# Shopping Cart Secure Configuration

This folder stores Helm value overlays. The `shopping-cart-eso` Vault policy is written by `shopping-integration/scripts/bootstrap-vault.sh`.
It never stores plaintext application credentials, Vault tokens, or unseal keys.

Each release applies its chart defaults, then its release-specific file under `values/local/`.
Vault initialization material is stored in macOS Keychain by the bootstrap scripts
from the `shopping-integration` repository.

