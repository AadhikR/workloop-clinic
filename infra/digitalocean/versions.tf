terraform {
  required_version = ">= 1.16.1, < 1.17.0"

  backend "local" {}

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "2.100.0"
    }
  }
}

provider "digitalocean" {}
