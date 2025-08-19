-- Storage RLS Policies for voice-lines bucket
-- Apply this in Supabase Dashboard > Storage > voice-lines bucket > Policies

-- Policy 1: Users can only INSERT files in their own private directory
CREATE POLICY "Users can upload to own directory" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'voice-lines' 
        AND (storage.foldername(name))[1] = 'private'
        AND (storage.foldername(name))[2] = auth.uid()::text
    );

-- Policy 2: Users can only SELECT their own files
CREATE POLICY "Users can view own files" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'voice-lines' 
        AND (storage.foldername(name))[1] = 'private'
        AND (storage.foldername(name))[2] = auth.uid()::text
    );

-- Policy 3: Users can only UPDATE their own files
CREATE POLICY "Users can update own files" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'voice-lines' 
        AND (storage.foldername(name))[1] = 'private'
        AND (storage.foldername(name))[2] = auth.uid()::text
    );

-- Policy 4: Users can only DELETE their own files
CREATE POLICY "Users can delete own files" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'voice-lines' 
        AND (storage.foldername(name))[1] = 'private'
        AND (storage.foldername(name))[2] = auth.uid()::text
    );