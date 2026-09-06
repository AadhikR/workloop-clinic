import uuid
from collections.abc import Collection, Sequence
from typing import Any, cast

from sqlalchemy import ColumnElement, Delete, Select, Update, delete, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import SQLColumnExpression
from sqlalchemy.sql.selectable import FromClause

from app.schemas.mutations import GuardedMutationValues


class ResourceNotFoundError(Exception):
    pass


class InvalidBatchError(ValueError):
    pass


class MutationConflictError(Exception):
    pass


def build_scoped_select(
    table: FromClause,
    scope_predicate: ColumnElement[bool],
    *,
    columns: Sequence[SQLColumnExpression[Any]] = (),
    extra_predicates: Sequence[ColumnElement[bool]] = (),
) -> Select[Any]:
    selected: tuple[Any, ...] = tuple(columns) if columns else (table,)
    return select(*selected).select_from(table).where(scope_predicate, *extra_predicates)


def build_scoped_lookup(
    table: FromClause,
    id_column: SQLColumnExpression[uuid.UUID],
    object_id: object,
    scope_predicate: ColumnElement[bool],
    *,
    columns: Sequence[SQLColumnExpression[Any]] = (),
    extra_predicates: Sequence[ColumnElement[bool]] = (),
    for_update: bool = False,
) -> Select[Any]:
    statement = build_scoped_select(
        table,
        scope_predicate,
        columns=columns,
        extra_predicates=(id_column == object_id, *extra_predicates),
    ).limit(1)
    return statement.with_for_update() if for_update else statement


def build_scoped_update(
    table: FromClause,
    id_column: SQLColumnExpression[uuid.UUID],
    object_ids: Collection[uuid.UUID],
    scope_predicate: ColumnElement[bool],
    values: GuardedMutationValues,
    *,
    extra_predicates: Sequence[ColumnElement[bool]] = (),
) -> Update:
    normalized_ids = _normalize_batch_ids(object_ids)
    if not isinstance(cast(object, values), GuardedMutationValues):
        raise TypeError("scoped updates require values issued by a mutation field guard")
    if not values:
        raise ValueError("a scoped update requires at least one value")
    return (
        update(cast(Any, table))
        .where(
            id_column.in_(normalized_ids),
            scope_predicate,
            *extra_predicates,
        )
        .values(**dict(values))
    )


def build_scoped_delete(
    table: FromClause,
    id_column: SQLColumnExpression[uuid.UUID],
    object_ids: Collection[uuid.UUID],
    scope_predicate: ColumnElement[bool],
    *,
    extra_predicates: Sequence[ColumnElement[bool]] = (),
) -> Delete:
    normalized_ids = _normalize_batch_ids(object_ids)
    return delete(cast(Any, table)).where(
        id_column.in_(normalized_ids),
        scope_predicate,
        *extra_predicates,
    )


def _normalize_batch_ids(object_ids: Collection[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    normalized = tuple(object_ids)
    if not normalized:
        raise InvalidBatchError("a scoped batch cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise InvalidBatchError("a scoped batch cannot contain duplicate identifiers")
    return normalized


class ScopedRepository:
    def __init__(
        self,
        *,
        connection: AsyncConnection,
        table: FromClause,
        id_column: SQLColumnExpression[uuid.UUID],
        scope_predicate: ColumnElement[bool],
    ) -> None:
        self._connection = connection
        self._table = table
        self._id_column = id_column
        self._scope_predicate = scope_predicate

    async def fetch_one(
        self,
        object_id: object,
        *,
        columns: Sequence[SQLColumnExpression[Any]] = (),
        extra_predicates: Sequence[ColumnElement[bool]] = (),
        for_update: bool = False,
    ) -> RowMapping:
        statement = build_scoped_lookup(
            self._table,
            self._id_column,
            object_id,
            self._scope_predicate,
            columns=columns,
            extra_predicates=extra_predicates,
            for_update=for_update,
        )
        result = await self._connection.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def fetch_many(
        self,
        *,
        columns: Sequence[SQLColumnExpression[Any]] = (),
        extra_predicates: Sequence[ColumnElement[bool]] = (),
    ) -> Sequence[RowMapping]:
        statement = build_scoped_select(
            self._table,
            self._scope_predicate,
            columns=columns,
            extra_predicates=extra_predicates,
        )
        result = await self._connection.execute(statement)
        return result.mappings().all()

    async def lock_batch(
        self,
        object_ids: Collection[uuid.UUID],
    ) -> tuple[uuid.UUID, ...]:
        normalized_ids = _normalize_batch_ids(object_ids)
        statement = (
            build_scoped_select(
                self._table,
                self._scope_predicate,
                columns=(self._id_column,),
                extra_predicates=(self._id_column.in_(normalized_ids),),
            )
            .order_by(self._id_column)
            .with_for_update()
        )
        result = await self._connection.execute(statement)
        visible_ids = tuple(result.scalars().all())
        if set(visible_ids) != set(normalized_ids) or len(visible_ids) != len(normalized_ids):
            raise ResourceNotFoundError
        return normalized_ids

    async def update_one(
        self,
        object_id: uuid.UUID,
        values: GuardedMutationValues,
        *,
        extra_predicates: Sequence[ColumnElement[bool]] = (),
    ) -> None:
        await self.update_batch(
            (object_id,),
            values,
            extra_predicates=extra_predicates,
        )

    async def update_batch(
        self,
        object_ids: Collection[uuid.UUID],
        values: GuardedMutationValues,
        *,
        extra_predicates: Sequence[ColumnElement[bool]] = (),
    ) -> None:
        normalized_ids = _normalize_batch_ids(object_ids)
        statement = build_scoped_update(
            self._table,
            self._id_column,
            normalized_ids,
            self._scope_predicate,
            values,
            extra_predicates=extra_predicates,
        )
        async with self._connection.begin_nested():
            await self.lock_batch(normalized_ids)
            result = await self._connection.execute(statement)
            if result.rowcount != len(normalized_ids):
                raise MutationConflictError

    async def delete_one(
        self,
        object_id: uuid.UUID,
        *,
        extra_predicates: Sequence[ColumnElement[bool]] = (),
    ) -> None:
        await self.delete_batch((object_id,), extra_predicates=extra_predicates)

    async def delete_batch(
        self,
        object_ids: Collection[uuid.UUID],
        *,
        extra_predicates: Sequence[ColumnElement[bool]] = (),
    ) -> None:
        normalized_ids = _normalize_batch_ids(object_ids)
        statement = build_scoped_delete(
            self._table,
            self._id_column,
            normalized_ids,
            self._scope_predicate,
            extra_predicates=extra_predicates,
        )
        async with self._connection.begin_nested():
            await self.lock_batch(normalized_ids)
            result = await self._connection.execute(statement)
            if result.rowcount != len(normalized_ids):
                raise MutationConflictError
