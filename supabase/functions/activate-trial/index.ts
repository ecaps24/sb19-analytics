import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const DASHBOARD_URL = 'https://ecaps24.github.io/sb19-analytics/';
const VALID_TRIAL_TIERS = ['basic', 'plus'];

Deno.serve(async (req: Request) => {
  try {
    const url = new URL(req.url);
    const tier = url.searchParams.get('tier');
    const token = url.searchParams.get('token');

    // Validate inputs
    if (!token) {
      return Response.redirect(`${DASHBOARD_URL}?trial=error&msg=missing_token`, 302);
    }
    if (!tier || !VALID_TRIAL_TIERS.includes(tier)) {
      return Response.redirect(`${DASHBOARD_URL}?trial=error&msg=invalid_tier`, 302);
    }

    // Verify user from token
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: `Bearer ${token}` } } }
    );

    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return Response.redirect(`${DASHBOARD_URL}?trial=error&msg=unauthorized`, 302);
    }

    // Use service role for profile updates
    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Check if user already used a trial (one trial per account)
    const { data: profile, error: profileError } = await supabaseAdmin
      .from('profiles')
      .select('trial_tier')
      .eq('id', user.id)
      .single();

    if (profileError) {
      throw new Error('Could not load profile');
    }

    if (profile.trial_tier) {
      return Response.redirect(`${DASHBOARD_URL}?trial=error&msg=already_used`, 302);
    }

    // Activate 7-day trial
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7);

    const { error: updateError } = await supabaseAdmin
      .from('profiles')
      .update({
        subscription_tier: tier,
        subscription_status: 'active',
        subscription_expires_at: expiresAt.toISOString(),
        trial_tier: tier,
        trial_activated_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', user.id);

    if (updateError) {
      throw new Error(`Trial activation failed: ${updateError.message}`);
    }

    console.log(`Trial activated for user ${user.id}: ${tier} (expires ${expiresAt.toISOString()})`);

    return Response.redirect(`${DASHBOARD_URL}?trial=success&tier=${tier}`, 302);
  } catch (err) {
    console.error('activate-trial error:', err);
    return Response.redirect(
      `${DASHBOARD_URL}?trial=error&msg=${encodeURIComponent(err.message || 'server_error')}`,
      302
    );
  }
});
