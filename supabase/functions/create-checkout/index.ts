import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { handleCors, getCorsHeaders } from '../_shared/cors.ts';
import { createCheckoutSession } from '../_shared/paymongo.ts';

const TIER_PRICES: Record<string, { amount: number; name: string }> = {
  basic: { amount: 9900, name: 'SB19 Analytics — Basic Plan (Monthly)' },
  premium: { amount: 19900, name: 'SB19 Analytics — Premium Plan (Monthly)' },
};

const DASHBOARD_URL = 'https://ecaps24.github.io/sb19-analytics/';

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  const corsResp = handleCors(req);
  if (corsResp) return corsResp;

  const headers = getCorsHeaders(req);

  try {
    if (req.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // Verify user is authenticated
    const authHeader = req.headers.get('Authorization');
    if (!authHeader) {
      return new Response(JSON.stringify({ error: 'Missing authorization' }), {
        status: 401,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: authHeader } } }
    );

    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // Parse request body
    const { tier } = await req.json();

    if (!tier || !TIER_PRICES[tier]) {
      return new Response(
        JSON.stringify({ error: 'Invalid tier. Must be "basic" or "premium".' }),
        {
          status: 400,
          headers: { ...headers, 'Content-Type': 'application/json' },
        }
      );
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

    // Insert pending payment record (use service role for insert)
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

    return new Response(
      JSON.stringify({ checkout_url: checkoutUrl }),
      {
        status: 200,
        headers: { ...headers, 'Content-Type': 'application/json' },
      }
    );
  } catch (err) {
    console.error('create-checkout error:', err);
    return new Response(
      JSON.stringify({ error: err.message || 'Internal server error' }),
      {
        status: 500,
        headers: { ...headers, 'Content-Type': 'application/json' },
      }
    );
  }
});
