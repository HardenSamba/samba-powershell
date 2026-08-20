"""Derivation of the Enabled property from userAccountControl."""

from __future__ import annotations

# Enabled is not a directory attribute. It is the ACCOUNTDISABLE bit of
# userAccountControl, read the other way round. Contract 6.1 forbids
# inventing an attribute for it.
ACCOUNTDISABLE = 0x0002


# Tells whether an account is enabled, from its userAccountControl value.
def is_enabled(user_account_control: int) -> bool:
    return not user_account_control & ACCOUNTDISABLE
