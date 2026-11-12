INSERT INTO users
    (id, email, password_hash, role, display_name, status, email_verified,
     auth_provider, external_subject, created_at)
VALUES
    (1, 'client@native.invalid', '', 'client', 'Fixture consumer', 'active', 1, 'clerk', 'user_native_client', '2000-01-01T00:00:00+00:00'),
    (2, 'contractor@native.invalid', '', 'contractor', 'Fixture contractor', 'active', 1, 'clerk', 'user_native_contractor', '2000-01-01T00:00:00+00:00'),
    (3, 'other-client@native.invalid', '', 'client', 'Other fixture consumer', 'active', 1, 'clerk', 'user_native_other_client', '2000-01-01T00:00:00+00:00'),
    (4, 'other-contractor@native.invalid', '', 'contractor', 'Other fixture contractor', 'active', 1, 'clerk', 'user_native_other_contractor', '2000-01-01T00:00:00+00:00'),
    (5, 'admin@native.invalid', '', 'admin', 'Fixture moderator', 'active', 1, 'clerk', 'user_native_admin', '2000-01-01T00:00:00+00:00'),
    (6, 'suspended@native.invalid', '', 'contractor', 'Suspended fixture', 'suspended', 1, 'clerk', 'user_native_suspended', '2000-01-01T00:00:00+00:00'),
    (7, 'webhook-fixture@native.invalid', '', 'contractor', 'Webhook fixture', 'active', 1, 'clerk', 'user_native_webhook', '2000-01-01T00:00:00+00:00');

INSERT INTO client_profiles (user_id, organization_name) VALUES (1, ''), (3, '');
INSERT INTO contractor_profiles (user_id, business_name, trades, service_area, updated_at)
VALUES (2, 'Fixture contractor', 'Window cleaning', 'Alexandria, VA', '2000-01-01T00:00:00+00:00'),
       (4, 'Other fixture contractor', 'Window cleaning', 'Alexandria, VA', '2000-01-01T00:00:00+00:00');

UPDATE contractor_profiles
SET intro = 'First synthetic line' || char(13) || char(10) || 'Second synthetic line; quoted ''scope'''
WHERE user_id = 2;
