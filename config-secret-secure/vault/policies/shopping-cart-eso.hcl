path "secret/data/shopping-cart/*" {
  capabilities = ["read"]
}

path "secret/metadata/shopping-cart/*" {
  capabilities = ["read", "list"]
}

