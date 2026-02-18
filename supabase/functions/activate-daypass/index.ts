import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const DASHBOARD_URL = 'https://ecaps24.github.io/sb19-analytics/';

Deno.serve(async (req: Request) => {
  try {
    const url = new URL(req.url);
    const token = url.searchParams.get('token');

    if (!token) {
      return Response.redirect(`${DASHBOARD_URL}?daypass=error&msg=missing_token`, 302);
    }

    // Verify user from token
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: `Bearer ${token}` } } }
    );

    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return Response.redirect(`${DASHBOARD_URL}?daypass=error&msg=unauthorized`, 302);
    }

    // Use service role for profile updates (bypasses RLS)
    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Activate 24-hour day pass
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 1);

    const { error: updateError } = await supabaseAdmin
      .from('profiles')
      .update({
        subscription_tier: 'daypass',
        subscription_status: 'active',
        subscription_expires_at: expiresAt.toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', user.id);

    if (updateError) {
      throw new Error(`Day pass activation failed: ${updateError.message}`);
    }

    console.log(`Day pass activated for user ${user.id} (expires ${expiresAt.toISOString()})`);

    return Response.redirect(`${DASHBOARD_URL}?daypass=success`, 302);
  } catch (err) {
    console.error('activate-daypass error:', err);
    return Response.redirect(
      `${DASHBOARD_URL}?daypass=error&msg=${encodeURIComponent(err.message || 'server_error')}`,
      302
    );
  }
});
