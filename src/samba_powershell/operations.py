"""Directory read operations exposed through the backend protocol."""

from __future__ import annotations

from samba_powershell import parameters, render
from samba_powershell.client_error import translate_client_error
from samba_powershell.client_loader import ClientFactory
from samba_powershell.errors import BackendError
from samba_powershell.guards import class_guard, wire_identity
from samba_powershell.object_classes import SPECS, ClassSpec

ADWS_PORT = 9389
ADWS_TIMEOUT = 30.0

# The attribute fetch behind the decided Get-ADUser default set, re-exported
# under the name the tests and the documentation already use.
DEFAULT_USER_PROPERTIES = SPECS["user"].fetch


# Retrieves one object of a known class through the samba-adws client boundary.
def get_object(request: dict[str, object], client_factory: ClientFactory,
               spec: ClassSpec) -> dict[str, object]:
    parameters.validate_parameters(request)
    identity = wire_identity(parameters.required_string(request, "identity"))
    server = parameters.requested_server(request)
    extras = parameters.requested_extras(request)
    fetch = parameters.fetch_list(spec.fetch, extras)
    try:
        client = client_factory(server, ADWS_PORT, ADWS_TIMEOUT)
        attributes = dict(client.get_by_dn(identity, fetch))
    except BackendError:
        raise
    except Exception as exc:
        raise translate_client_error(exc) from exc
    class_guard(spec, attributes, identity)
    return {"type": spec.type_name, "properties": render.render(attributes, spec, extras)}


# Retrieves one user.
def get_ad_user(request: dict[str, object],
                client_factory: ClientFactory) -> dict[str, object]:
    return get_object(request, client_factory, SPECS["user"])


# Retrieves one computer.
def get_ad_computer(request: dict[str, object],
                    client_factory: ClientFactory) -> dict[str, object]:
    return get_object(request, client_factory, SPECS["computer"])


# Retrieves one group.
def get_ad_group(request: dict[str, object],
                 client_factory: ClientFactory) -> dict[str, object]:
    return get_object(request, client_factory, SPECS["group"])


# Retrieves one object of any class.
def get_ad_object(request: dict[str, object],
                  client_factory: ClientFactory) -> dict[str, object]:
    return get_object(request, client_factory, SPECS["object"])
