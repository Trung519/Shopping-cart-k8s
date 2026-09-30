# Shopping Cart Secure Configuration

This private repository stores Helm value overlays and Vault policy definitions.
It never stores plaintext application credentials, Vault tokens, or unseal keys.

Values are applied in order: `00-global.yaml`, then the release-specific file.
Vault initialization material is stored in macOS Keychain by the bootstrap scripts
from the `shopping-integration` repository.

