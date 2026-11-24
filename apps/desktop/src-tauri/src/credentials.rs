use keyring::Entry;
use serde::Serialize;

const SERVICE_NAME: &str = "digital.ngoprek.omnidesk";

#[derive(Debug, Serialize)]
pub struct CredentialStatus {
    pub provider_id: String,
    pub configured: bool,
    pub masked_hint: Option<String>,
}

fn validate_provider_id(provider_id: &str) -> Result<(), String> {
    if matches!(
        provider_id,
        "openai" | "gemini" | "anthropic" | "ollama" | "openai_compatible"
    ) {
        Ok(())
    } else {
        Err(format!("Unsupported provider identifier: {provider_id}"))
    }
}

pub fn mask_secret(secret: &str) -> String {
    let trimmed = secret.trim();
    if trimmed.len() <= 8 {
        return "****".to_string();
    }
    format!("{}...{}", &trimmed[..4], &trimmed[trimmed.len() - 4..])
}

pub fn store_secret(provider_id: &str, api_key: &str) -> Result<CredentialStatus, String> {
    validate_provider_id(provider_id)?;
    let trimmed = api_key.trim();
    if trimmed.len() < 8 {
        return Err("API key appears too short to be valid.".into());
    }
    let entry = Entry::new(SERVICE_NAME, provider_id)
        .map_err(|e| format!("Could not access OS credential store: {e}"))?;
    entry
        .set_password(trimmed)
        .map_err(|e| format!("Could not save key in OS credential store: {e}"))?;
    Ok(CredentialStatus {
        provider_id: provider_id.to_string(),
        configured: true,
        masked_hint: Some(mask_secret(trimmed)),
    })
}

pub fn check_secret(provider_id: &str) -> Result<CredentialStatus, String> {
    validate_provider_id(provider_id)?;
    let entry = Entry::new(SERVICE_NAME, provider_id)
        .map_err(|e| format!("Could not access OS credential store: {e}"))?;
    match entry.get_password() {
        Ok(secret) if !secret.trim().is_empty() => Ok(CredentialStatus {
            provider_id: provider_id.to_string(),
            configured: true,
            masked_hint: Some(mask_secret(&secret)),
        }),
        _ => Ok(CredentialStatus {
            provider_id: provider_id.to_string(),
            configured: false,
            masked_hint: None,
        }),
    }
}

pub fn delete_secret(provider_id: &str) -> Result<CredentialStatus, String> {
    validate_provider_id(provider_id)?;
    let entry = Entry::new(SERVICE_NAME, provider_id)
        .map_err(|e| format!("Could not access OS credential store: {e}"))?;
    let _ = entry.delete_credential();
    Ok(CredentialStatus {
        provider_id: provider_id.to_string(),
        configured: false,
        masked_hint: None,
    })
}

#[cfg(test)]
mod tests {
    use super::{mask_secret, validate_provider_id};

    #[test]
    fn masks_secrets_without_exposing_middle() {
        assert_eq!(mask_secret("sk-proj-1234567890abcdef"), "sk-p...cdef");
        assert_eq!(mask_secret("short"), "****");
    }

    #[test]
    fn rejects_unknown_providers() {
        assert!(validate_provider_id("openai").is_ok());
        assert!(validate_provider_id("untrusted_provider").is_err());
    }
}
