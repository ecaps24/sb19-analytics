-- Allow admin users to read all profiles
-- Run this in Supabase SQL Editor
-- Works alongside existing "Users can read own profile" policy (OR logic for SELECT)

CREATE POLICY "Admins can read all profiles"
  ON public.profiles FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE id = auth.uid() AND is_admin = true
    )
  );
