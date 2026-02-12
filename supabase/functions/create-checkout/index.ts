import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { createCheckoutSession } from '../_shared/paymongo.ts';

const TIER_PRICES: Record<string, { amount: number; name: string }> = {
  basic: { amount: 4900, name: 'SB19 Analytics — Basic Plan (Monthly)' },
  plus: { amount: 9900, name: 'SB19 Analytics — Plus Plan (Monthly)' },
  premium: { amount: 29900, name: 'SB19 Analytics — Premium Plan (Monthly)' },
};

const DASHBOARD_URL = 'https://ecaps24.github.io/sb19-analytics/';

Deno.serve(async (req: Request) => {
  try {
    const url = new URL(req.url);
    const tier = url.searchParams.get('tier');
    const token = url.searchParams.get('token');

    // Validate inputs
    if (!token) {
      return Response.redirect(`${DASHBOARD_URL}?payment=error&msg=missing_token`, 302);
    }
    if (!tier || !TIER_PRICES[tier]) {
      return Response.redirect(`${DASHBOARD_URL}?payment=error&msg=invalid_tier`, 302);
    }

    // Verify user from token
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: `Bearer ${token}` } } }
    );

    const { data: { user }, error: authError } = await supabase.auth.getUser();
    if (authError || !user) {
      return Response.redirect(`${DASHBOARD_URL}?payment=error&msg=unauthorized`, 302);
    }

    const priceInfo = TIER_PRICES[tier];
    const paymongoSecretKey = Deno.env.get('PAYMONGO_SECRET_KEY');
    if (!paymongoSecretKey) {
      throw new Error('PAYMONGO_SECRET_KEY not configured');
    }

    // Create PayMongo Checkout Session
    const checkoutResult = await createCheckoutSession(paymongoSecretKey, {
      lineItems: [
        {
          name: priceInfo.name,
          amount: priceInfo.amount,
          currency: 'PHP',
          quantity: 1,
        },
      ],
      description: `Subscription upgrade to ${tier} plan`,
      metadata: {
        user_id: user.id,
        user_email: user.email || '',
        tier,
      },
      successUrl: `${DASHBOARD_URL}?payment=success`,
      cancelUrl: `${DASHBOARD_URL}?payment=cancelled`,
    });

    const checkoutId = checkoutResult.data.id;
    const checkoutUrl = checkoutResult.data.attributes.checkout_url;

    // Insert pending payment record
    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    await supabaseAdmin.from('payments').insert({
      user_id: user.id,
      paymongo_checkout_id: checkoutId,
      tier,
      amount: priceInfo.amount,
      currency: 'PHP',
      status: 'pending',
    });

    // Redirect directly to PayMongo checkout — no CORS needed
    return Response.redirect(checkoutUrl, 302);
  } catch (err) {
    console.error('create-checkout error:', err);
    return Response.redirect(
      `${DASHBOARD_URL}?payment=error&msg=${encodeURIComponent(err.message || 'server_error')}`,
      302
    );
  }
});
