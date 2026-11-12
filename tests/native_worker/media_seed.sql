INSERT INTO job_photos
    (id, job_id, uploaded_by, original_filename, stored_path, content_type,
     size_bytes, is_hidden, created_at)
VALUES
    (9101, 1, 1, 'private-source-name.webp', 'jobs/1/native.webp', 'image/webp', 16502, 0, '2000-01-01T00:00:00+00:00'),
    (9102, 1, 1, 'private-source-name.webp', 'jobs/1/missing.webp', 'image/webp', 16502, 0, '2000-01-01T00:00:00+00:00'),
    (9103, 1, 1, 'private-source-name.webp', 'jobs/99/native.webp', 'image/webp', 16502, 0, '2000-01-01T00:00:00+00:00'),
    (9104, 1, 1, 'private-source-name.webp', 'jobs/1/native.webp', 'image/webp', 16502, 1, '2000-01-01T00:00:00+00:00');

INSERT INTO contractor_photos
    (id, contractor_id, original_filename, stored_path, content_type,
     size_bytes, is_hidden, created_at)
VALUES
    (9201, 2, 'private-source-name.webp', 'contractors/2/native.webp', 'image/webp', 16502, 0, '2000-01-01T00:00:00+00:00'),
    (9202, 2, 'private-source-name.webp', 'contractors/2/native.webp', 'image/webp', 16502, 1, '2000-01-01T00:00:00+00:00');
