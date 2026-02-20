-- Allow admin users to read all profiles
-- Run this in Supabase SQL Editor
-- Works alongside existing "Users can read own profile" policy (OR logic for SELECT)

-- Step 1: Security-definer function to check admin status without triggering RLS
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND is_admin = true
  );
$$;

-- Step 2: Drop the old recursive policy (if it exists)
DROP POLICY IF EXISTS "Admins can read all profiles" ON public.profiles;

-- Step 3: Recreate using the helper function (avoids infinite recursion)
CREATE POLICY "Admins can read all profiles"
  ON public.profiles FOR SELECT
  USING (public.is_admin());
