-- ============================================================
-- SB19 Analytics — Supabase Database Setup
-- Run this entire script in Supabase SQL Editor (one shot)
-- Dashboard > SQL Editor > New query > Paste & Run
-- ============================================================

-- Step 1: Create profiles table
CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT,
  full_name TEXT DEFAULT '',
  subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'basic', 'plus', 'premium')),
  is_admin BOOLEAN DEFAULT false,
  trial_tier TEXT DEFAULT NULL,
  trial_activated_at TIMESTAMPTZ DEFAULT NULL,
  subscription_status TEXT DEFAULT 'inactive' CHECK (subscription_status IN ('active', 'inactive')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Step 2: Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data ->> 'full_name', '')
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- Step 3: Enable Row Level Security
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "Users can read own profile"
  ON public.profiles FOR SELECT
  USING (auth.uid() = id);

-- Users can update own profile (but NOT subscription_tier, subscription_status, or is_admin)
CREATE POLICY "Users can update own profile"
  ON public.profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (
    auth.uid() = id
    AND subscription_tier = (SELECT subscription_tier FROM public.profiles WHERE id = auth.uid())
    AND subscription_status = (SELECT subscription_status FROM public.profiles WHERE id = auth.uid())
    AND is_admin = (SELECT is_admin FROM public.profiles WHERE id = auth.uid())
  );

-- Step 4: Updated_at auto-timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at();

-- ============================================================
-- Step 5: PayMongo Payment Integration
-- ============================================================

-- Add subscription expiry tracking to profiles
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMPTZ DEFAULT NULL;

-- Payments audit log
CREATE TABLE IF NOT EXISTS public.payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  paymongo_checkout_id TEXT,
  paymongo_payment_id TEXT,
  tier TEXT NOT NULL CHECK (tier IN ('basic', 'plus', 'premium')),
  amount INTEGER NOT NULL,
  currency TEXT DEFAULT 'PHP',
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'expired')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS for payments
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

-- Users can read their own payment history
CREATE POLICY "Users can read own payments"
  ON public.payments FOR SELECT
  USING (auth.uid() = user_id);

-- Auto-update updated_at for payments
CREATE TRIGGER payments_updated_at
  BEFORE UPDATE ON public.payments
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at();

-- ============================================================
-- Step 6: Set admin user
-- ============================================================
UPDATE public.profiles SET is_admin = true WHERE email = 'edwin.f.capidos@gmail.com';
