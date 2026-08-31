from __future__ import annotations

import base64
import hashlib
import html.parser
import http.cookiejar
import json
import os
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
REALM_FILE = ROOT / "keycloak" / "realm" / "workloop-dev-realm.json"
BASE_URL = "http://127.0.0.1:8080"
REALM_URL = f"{BASE_URL}/realms/workloop-dev"
CLIENT_ID = "workloop-migration-web"
REDIRECT_URI = "http://127.0.0.1:5174/auth/callback"
LOGOUT_URI = "http://127.0.0.1:5174/"
ORIGIN = "http://127.0.0.1:5174"
KCADM_CONFIG = "/tmp/workloop-phase-3c-kcadm.config"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


OPENER = urllib.request.build_opener(NoRedirect)


class LoginFormParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "form" and attributes.get("id") == "kc-form-login":
            self.action = attributes.get("action")


def docker_path() -> str:
    configured = os.environ.get("DOCKER")
    if configured:
        return configured
    found = shutil.which("docker")
    if found:
        return found
    windows_path = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    if windows_path.exists():
        return str(windows_path)
    raise RuntimeError("Docker executable not found")


DOCKER_COMPOSE = [docker_path(), "compose"]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*DOCKER_COMPOSE, *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def kcadm(*args: str) -> str:
    result = run(
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        *args,
        "--config",
        KCADM_CONFIG,
    )
    return result.stdout


def kcadm_json(*args: str) -> Any:
    return json.loads(kcadm(*args))


def verify_stage(name: str, check: Callable[[], None]) -> None:
    try:
        check()
    except AssertionError as error:
        detail = str(error) or "assertion failed"
        raise AssertionError(f"{name}: {detail}") from error


def request(
    url: str,
    *,
    data: dict[str, str] | None = None,
) -> tuple[int, Any, bytes]:
    encoded = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=encoded)
    try:
        response = OPENER.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    with response:
        return response.status, response.headers, response.read()


def authorization_request(
    *,
    redirect_uri: str = REDIRECT_URI,
    response_type: str = "code",
    code_challenge: str | None = "A" * 43,
    code_challenge_method: str | None = "S256",
) -> tuple[int, Any, bytes]:
    params = {
        "client_id": CLIENT_ID,
        "response_type": response_type,
        "scope": "openid profile email",
        "redirect_uri": redirect_uri,
        "state": "phase-3c-state",
        "nonce": "phase-3c-nonce",
    }
    if code_challenge is not None:
        params["code_challenge"] = code_challenge
    if code_challenge_method is not None:
        params["code_challenge_method"] = code_challenge_method
    url = f"{REALM_URL}/protocol/openid-connect/auth?{urllib.parse.urlencode(params)}"
    return request(url)


def assert_source_is_sanitized(realm: dict[str, Any]) -> None:
    forbidden_keys = {
        "apikey",
        "certificate",
        "clientsecret",
        "components",
        "credentials",
        "federatedusers",
        "privatekey",
        "publickey",
        "secret",
        "signingkey",
        "password",
        "token",
        "users",
    }

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                assert key.lower() not in forbidden_keys, f"forbidden realm field: {key}"
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(realm)
    assert realm["smtpServer"] == {}


def verify_realm(realm: dict[str, Any]) -> None:
    expected = {
        "realm": "workloop-dev",
        "enabled": True,
        "sslRequired": "external",
        "registrationAllowed": False,
        "rememberMe": False,
        "verifyEmail": False,
        "resetPasswordAllowed": False,
        "editUsernameAllowed": False,
        "loginWithEmailAllowed": True,
        "duplicateEmailsAllowed": False,
        "defaultSignatureAlgorithm": "RS256",
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "clientSessionIdleTimeout": 0,
        "clientSessionMaxLifespan": 0,
        "revokeRefreshToken": True,
        "refreshTokenMaxReuse": 0,
        "bruteForceProtected": True,
        "permanentLockout": False,
        "maxTemporaryLockouts": 0,
        "bruteForceStrategy": "MULTIPLE",
        "failureFactor": 5,
        "waitIncrementSeconds": 60,
        "maxFailureWaitSeconds": 900,
        "maxDeltaTimeSeconds": 43200,
        "quickLoginCheckMilliSeconds": 1000,
        "minimumQuickLoginWaitSeconds": 60,
        "maxSecondaryAuthFailures": 0,
        "smtpServer": {},
    }
    for key, value in expected.items():
        assert realm.get(key) == value, f"unexpected realm setting {key}: {realm.get(key)!r}"


def only_client(clients: Any, client_id: str) -> dict[str, Any]:
    assert isinstance(clients, list) and len(clients) == 1, f"expected one {client_id} client"
    client = clients[0]
    assert client["clientId"] == client_id
    return client


def verify_clients(web: dict[str, Any], api: dict[str, Any]) -> None:
    assert web["enabled"] is True
    assert web["publicClient"] is True
    assert web["bearerOnly"] is False
    assert web["standardFlowEnabled"] is True
    assert web["implicitFlowEnabled"] is False
    assert web["directAccessGrantsEnabled"] is False
    assert web["serviceAccountsEnabled"] is False
    assert web.get("authorizationServicesEnabled", False) is False
    assert web["fullScopeAllowed"] is False
    assert web["redirectUris"] == [REDIRECT_URI]
    assert web["webOrigins"] == [ORIGIN]
    assert web["defaultClientScopes"] == ["profile", "email"]
    assert web["optionalClientScopes"] == []
    assert "secret" not in web

    attributes = web["attributes"]
    assert attributes["pkce.code.challenge.method"] == "S256"
    assert attributes["post.logout.redirect.uris"] == LOGOUT_URI
    for setting in (
        "standard.token.exchange.enabled",
        "oauth2.device.authorization.grant.enabled",
        "oidc.ciba.grant.enabled",
        "oauth2.jwt.authorization.grant.enabled",
    ):
        assert attributes[setting] == "false"

    mappers = [mapper for mapper in web["protocolMappers"] if mapper["name"] == "workloop-api-audience"]
    assert len(mappers) == 1
    mapper = mappers[0]
    assert mapper["protocolMapper"] == "oidc-audience-mapper"
    assert mapper["config"]["included.client.audience"] == "workloop-api"
    assert mapper["config"]["access.token.claim"] == "true"
    assert mapper["config"]["id.token.claim"] == "false"

    assert api["enabled"] is True
    assert api["bearerOnly"] is True
    assert api["publicClient"] is False
    assert api["standardFlowEnabled"] is False
    assert api["implicitFlowEnabled"] is False
    assert api["directAccessGrantsEnabled"] is False
    assert api["serviceAccountsEnabled"] is False
    assert api.get("authorizationServicesEnabled", False) is False
    assert api["fullScopeAllowed"] is False
    assert api["redirectUris"] == []
    assert api["webOrigins"] == []
    assert api["defaultClientScopes"] == []
    assert api["optionalClientScopes"] == []
    for setting in (
        "standard.token.exchange.enabled",
        "oauth2.device.authorization.grant.enabled",
        "oidc.ciba.grant.enabled",
        "oauth2.jwt.authorization.grant.enabled",
    ):
        assert api["attributes"][setting] == "false"


def verify_protocol_restrictions() -> None:
    status, _, _ = authorization_request()
    assert status == 200, f"valid S256 authorization request returned {status}"

    for kwargs in (
        {"code_challenge": None, "code_challenge_method": None},
        {"code_challenge_method": "plain"},
    ):
        status, headers, _ = authorization_request(**kwargs)
        assert status == 302
        location = headers.get("Location", "")
        assert location.startswith(f"{REDIRECT_URI}?")
        assert "error=" in location
        assert "code=" not in location

    rejected_redirects = (
        "http://127.0.0.1:5174/",
        "http://127.0.0.1:5174/auth/callback/extra",
        "http://127.0.0.1:5173/auth/callback",
        "http://localhost:5174/auth/callback",
        "https://127.0.0.1:5174/auth/callback",
        "https://example.test/auth/callback",
    )
    for redirect_uri in rejected_redirects:
        status, headers, _ = authorization_request(redirect_uri=redirect_uri)
        assert status == 400, f"redirect was not rejected: {redirect_uri}"
        assert headers.get("Location") is None

    status, headers, _ = authorization_request(response_type="token")
    assert status == 302
    assert "error=" in headers.get("Location", "")

    token_url = f"{REALM_URL}/protocol/openid-connect/token"
    status, _, body = request(
        token_url,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "password",
            "username": "not-a-user",
            "password": "not-a-password",
        },
    )
    assert status == 400 and json.loads(body)["error"] == "unauthorized_client"

    status, _, body = request(
        token_url,
        data={"client_id": CLIENT_ID, "grant_type": "client_credentials"},
    )
    assert status == 401 and json.loads(body)["error"] == "unauthorized_client"

    status, _, body = request(
        f"{REALM_URL}/protocol/openid-connect/auth/device",
        data={"client_id": CLIENT_ID, "scope": "openid"},
    )
    assert status == 400 and json.loads(body)["error"] == "unauthorized_client"

    status, _, body = request(
        f"{REALM_URL}/protocol/openid-connect/ext/ciba/auth",
        data={"client_id": CLIENT_ID, "login_hint": "not-a-user"},
    )
    assert status == 401 and json.loads(body)["error"] == "invalid_grant"
    assert "Client not allowed OIDC CIBA Grant" in json.loads(body)["error_description"]

    logout_url = f"{REALM_URL}/protocol/openid-connect/logout"
    status, headers, _ = request(
        f"{logout_url}?{urllib.parse.urlencode({'client_id': CLIENT_ID, 'post_logout_redirect_uri': LOGOUT_URI})}"
    )
    assert status == 302 and headers.get("Location") == LOGOUT_URI

    for logout_uri in (
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5174/other",
        "http://localhost:5174/",
        "http://127.0.0.1:5173/",
        "https://example.test/",
    ):
        status, headers, _ = request(
            f"{logout_url}?{urllib.parse.urlencode({'client_id': CLIENT_ID, 'post_logout_redirect_uri': logout_uri})}"
        )
        assert status == 400, f"logout redirect was not rejected: {logout_uri}"
        assert headers.get("Location") is None


def decode_claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def authorize_with_login(
    username: str,
    password: str,
    verifier: str,
) -> tuple[str, urllib.request.OpenerDirector]:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": REDIRECT_URI,
        "state": "phase-3c-real-token",
        "nonce": "phase-3c-real-token",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))
    url = f"{REALM_URL}/protocol/openid-connect/auth?{urllib.parse.urlencode(params)}"
    try:
        response = opener.open(url, timeout=10)
        body = response.read().decode()
    except urllib.error.HTTPError as error:
        assert error.code == 302
        location = error.headers["Location"]
    else:
        parser = LoginFormParser()
        parser.feed(body)
        assert parser.action is not None
        login_data = urllib.parse.urlencode(
            {"username": username, "password": password, "credentialId": ""}
        ).encode()
        cookie_header = "; ".join(f"{cookie.name}={cookie.value}" for cookie in jar)
        login_request = urllib.request.Request(
            parser.action,
            data=login_data,
            headers={"Cookie": cookie_header},
        )
        try:
            opener.open(login_request, timeout=10)
        except urllib.error.HTTPError as error:
            assert error.code == 302
            location = error.headers["Location"]
        else:
            raise AssertionError("login did not return an authorization code")

    callback = urllib.parse.urlparse(location)
    callback_base = f"{callback.scheme}://{callback.netloc}{callback.path}"
    assert callback_base == REDIRECT_URI, f"unexpected callback target: {callback_base}"
    callback_params = urllib.parse.parse_qs(callback.query)
    assert callback_params["state"] == ["phase-3c-real-token"]
    return callback_params["code"][0], opener


def exchange_code(code: str, verifier: str) -> tuple[int, dict[str, Any]]:
    status, _, body = request(
        f"{REALM_URL}/protocol/openid-connect/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    return status, json.loads(body)


def verify_real_tokens(username: str, password: str) -> None:
    verifier = secrets.token_urlsafe(48)
    code, _ = authorize_with_login(username, password, verifier)
    status, tokens = exchange_code(code, verifier)
    assert status == 200

    access_claims = decode_claims(tokens["access_token"])
    audience = access_claims["aud"]
    assert audience == "workloop-api" or "workloop-api" in audience
    assert access_claims["azp"] == CLIENT_ID
    assert access_claims["typ"] == "Bearer"
    assert "offline_access" not in access_claims["scope"].split()

    id_claims = decode_claims(tokens["id_token"])
    assert id_claims["aud"] == CLIENT_ID
    assert id_claims.get("aud") != "workloop-api"

    refresh_token = tokens["refresh_token"]
    status, _, body = request(
        f"{REALM_URL}/protocol/openid-connect/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    assert status == 200
    refreshed = json.loads(body)
    refreshed_claims = decode_claims(refreshed["access_token"])
    refreshed_audience = refreshed_claims["aud"]
    assert refreshed_audience == "workloop-api" or "workloop-api" in refreshed_audience

    status, _, body = request(
        f"{REALM_URL}/protocol/openid-connect/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    assert status == 400 and json.loads(body)["error"] == "invalid_grant"

    second_verifier = secrets.token_urlsafe(48)
    second_code, _ = authorize_with_login(username, password, second_verifier)
    status, error = exchange_code(second_code, f"wrong-{second_verifier}")
    assert status == 400 and error["error"] == "invalid_grant"

    offline_params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email offline_access",
        "redirect_uri": REDIRECT_URI,
        "state": "phase-3c-offline",
        "nonce": "phase-3c-offline",
        "code_challenge": "A" * 43,
        "code_challenge_method": "S256",
    }
    status, headers, _ = request(
        f"{REALM_URL}/protocol/openid-connect/auth?{urllib.parse.urlencode(offline_params)}"
    )
    assert status == 302
    assert "error=invalid_scope" in headers.get("Location", "")


def verify_audience(web_client_id: str) -> None:
    username = "phase-3c-transient-protocol-test"
    password = secrets.token_urlsafe(32)
    user_id: str | None = None
    assert kcadm_json("get", "users", "-r", "workloop-dev", "-q", f"username={username}") == []
    try:
        kcadm(
            "create",
            "users",
            "-r",
            "workloop-dev",
            "-s",
            f"username={username}",
            "-s",
            "firstName=Phase",
            "-s",
            "lastName=Test",
            "-s",
            "email=phase-3c-transient@example.test",
            "-s",
            "enabled=true",
        )
        users = kcadm_json("get", "users", "-r", "workloop-dev", "-q", f"username={username}")
        assert len(users) == 1
        user_id = users[0]["id"]
        token = kcadm_json(
            "get",
            f"clients/{web_client_id}/evaluate-scopes/generate-example-access-token?userId={user_id}",
            "-r",
            "workloop-dev",
        )
        audience = token["aud"]
        assert audience == "workloop-api" or "workloop-api" in audience
        assert token["azp"] == CLIENT_ID
        assert token["typ"] == "Bearer"
        assert token["scope"] == "profile email"
        password_process = subprocess.run(
            [
                *DOCKER_COMPOSE,
                "exec",
                "-T",
                "keycloak",
                "sh",
                "-c",
                f'IFS= read -r password; /opt/keycloak/bin/kcadm.sh set-password --config {KCADM_CONFIG} '
                f'-r workloop-dev --userid {user_id} --new-password "$password" --temporary=false',
            ],
            cwd=ROOT,
            input=password,
            capture_output=True,
            text=True,
        )
        assert password_process.returncode == 0, "could not set transient test credential"
        verify_stage("real token flow", lambda: verify_real_tokens(username, password))
    finally:
        if user_id is not None:
            kcadm("delete", f"users/{user_id}", "-r", "workloop-dev")
    assert kcadm_json("get", "users", "-r", "workloop-dev", "-q", f"username={username}") == []


def main() -> None:
    source_realm = json.loads(REALM_FILE.read_text(encoding="utf-8"))
    assert_source_is_sanitized(source_realm)

    run(
        "exec",
        "-T",
        "keycloak",
        "sh",
        "-c",
        "/opt/keycloak/bin/kcadm.sh config credentials "
        f"--config {KCADM_CONFIG} --server http://127.0.0.1:8080 --realm master "
        '--user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" '
        ">/dev/null 2>&1",
    )
    try:
        realm = kcadm_json("get", "realms/workloop-dev")
        verify_stage("realm settings", lambda: verify_realm(realm))

        web = only_client(
            kcadm_json("get", "clients", "-r", "workloop-dev", "-q", f"clientId={CLIENT_ID}"),
            CLIENT_ID,
        )
        api = only_client(
            kcadm_json("get", "clients", "-r", "workloop-dev", "-q", "clientId=workloop-api"),
            "workloop-api",
        )
        verify_stage("client settings", lambda: verify_clients(web, api))
        assert kcadm_json("get", "users", "-r", "workloop-dev") == []
        verify_stage("audience and token checks", lambda: verify_audience(web["id"]))
        assert kcadm_json("get", "users", "-r", "workloop-dev") == []
        verify_stage("protocol restrictions", verify_protocol_restrictions)
    finally:
        run("exec", "-T", "keycloak", "rm", "-f", KCADM_CONFIG, check=False)

    print("Phase 3C Keycloak checks passed")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as error:
        detail = str(error) or error.__class__.__name__
        print(f"Phase 3C Keycloak checks failed: {detail}", file=sys.stderr)
        raise SystemExit(1) from error
