\connect workloop

DO $$
DECLARE
  signature pg_catalog.regprocedure;
  function_count integer := 0;
BEGIN
  FOR signature IN
    SELECT procedure.oid::pg_catalog.regprocedure
    FROM pg_catalog.pg_depend dependency
    JOIN pg_catalog.pg_extension extension ON extension.oid = dependency.refobjid
    JOIN pg_catalog.pg_proc procedure ON procedure.oid = dependency.objid
    WHERE dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
      AND dependency.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
      AND dependency.deptype = 'e'
      AND extension.extname = 'btree_gist'
  LOOP
    function_count := function_count + 1;
    EXECUTE pg_catalog.format('ALTER FUNCTION %s OWNER TO workloop_migration', signature);
    EXECUTE pg_catalog.format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', signature);
    EXECUTE pg_catalog.format(
      'GRANT EXECUTE ON FUNCTION %s TO workloop_migration, workloop_runtime, '
      'workloop_expiry_processing, workloop_file_scanner, workloop_storage_reconciler',
      signature
    );
  END LOOP;
  IF function_count = 0 THEN
    RAISE EXCEPTION 'btree_gist has no functions to secure';
  END IF;
END
$$;
