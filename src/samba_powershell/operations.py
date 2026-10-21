"""Directory read operations exposed through the backend protocol."""

from __future__ import annotations

from samba_powershell import parameters, properties, render
from samba_powershell.client_error import translate_client_error
from samba_powershell.client_loader import ClientFactory
from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.errors import BackendError
from samba_powershell.guards import class_guard
from samba_powershell.object_classes import SPECS, ClassSpec
from samba_powershell.resolve import wire_reference
from samba_powershell.schema import describe

ADWS_TIMEOUT = 30.0

# The attribute fetch behind the decided Get-ADUser default set, re-exported
# under the name the tests and the documentation already use.
DEFAULT_USER_PROPERTIES = SPECS["user"].fetch


# Retrieves one object of a known class through the samba-adws client boundary.
# Everything the client raises is translated at this one place, against the
# server and the identity the caller gave.
def get_object(request: dict[str, object], client_factory: ClientFactory,
               spec: ClassSpec) -> dict[str, object]:
    parameters.validate_parameters(request)
    identity = parameters.required_string(request, "identity")
    server, port = parameters.requested_endpoint(request)
    extras = properties.requested_extras(request)
    try:
        return read(client_factory(server, port, ADWS_TIMEOUT), identity, spec, extras)
    except BackendError:
        raise
    except Exception as exc:
        raise translate_client_error(exc, server, identity) from exc


# Resolves, reads, guards and renders one object on an open directory session.
# The schema is consulted only for the properties named, or for everything
# under -Properties *, so a read of the default set costs one exchange.
def read(directory: DirectoryClient, identity: str, spec: ClassSpec,
         extras: list[str]) -> dict[str, object]:
    reference = wire_reference(identity, spec, directory)
    fetch = properties.fetch_list(spec.fetch, extras)
    attributes = dict(directory.get_by_dn(reference, fetch))
    class_guard(spec, attributes, identity)
    schema = describe(directory, properties.typed_names(attributes, extras))
    properties.check_known(extras, schema)
    return {"type": spec.type_name, "properties": render.render(attributes, spec, extras, schema)}
