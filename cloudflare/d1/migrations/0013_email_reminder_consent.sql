ALTER TABLE client_profiles
ADD COLUMN email_reminder_consent_at TEXT;

-- Existing beta rows never recorded affirmative email-reminder consent.
UPDATE client_profiles
SET notification_preference = 'workdoe',
    email_reminder_consent_at = NULL;
