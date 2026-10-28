-- Source filenames can contain a name, street address, or other private detail.
-- Existing records retain only a generic label; new uploads are generic in code.
UPDATE job_photos
SET original_filename = CASE content_type
    WHEN 'image/webp' THEN 'workdoe-photo.webp'
    WHEN 'image/jpeg' THEN 'workdoe-photo.jpg'
    WHEN 'image/png' THEN 'workdoe-photo.png'
    WHEN 'image/gif' THEN 'workdoe-photo.gif'
    ELSE 'workdoe-photo'
END;

UPDATE contractor_photos
SET original_filename = CASE content_type
    WHEN 'image/webp' THEN 'workdoe-photo.webp'
    WHEN 'image/jpeg' THEN 'workdoe-photo.jpg'
    WHEN 'image/png' THEN 'workdoe-photo.png'
    WHEN 'image/gif' THEN 'workdoe-photo.gif'
    ELSE 'workdoe-photo'
END;
