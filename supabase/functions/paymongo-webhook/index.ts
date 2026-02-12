import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { handleCors, getCorsHeaders } from '../_shared/cors.ts';

async function verifyWebhookSignature(
  payload: string,
  signatureHeader: string,
  webhookSecret: string
): Promise<boolean> {
  // PayMongo signature format: t=<timestamp>,li=<live_signature>,te=<test_signature>
  const parts = signatureHeader.split(',');
  const timestampPart = parts.find((p) => p.startsWith('t='));
  const testSigPart = parts.find((p) => p.startsWith('te='));
  const liveSigPart = parts.find((p) => p.startsWith('li='));

  if (!timestampPart) return false;

  const timestamp = timestampPart.replace('t=', '');
  // Use test signature in test mode, live in production
  const signature = (testSigPart || liveSigPart)?.split('=').slice(1).join('=');
  if (!signature) return false;

  // Construct signed payload: timestamp.payload
  const signedPayload = `${timestamp}.${payload}`;

  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(webhookSecret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(signedPayload));
  const computedHex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  return computedHex === signature;
}

Deno.serve(async (req: Request) => {
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

    const rawBody = await req.text();
    const webhookSecret = Deno.env.get('PAYMONGO_WEBHOOK_SECRET');

    // Verify webhook signature if secret is configured
    if (webhookSecret) {
      const signatureHeader = req.headers.get('paymongo-signature') || '';
      const valid = await verifyWebhookSignature(rawBody, signatureHeader, webhookSecret);
      if (!valid) {
        console.error('Invalid webhook signature');
        return new Response(JSON.stringify({ error: 'Invalid signature' }), {
          status: 401,
          headers: { ...headers, 'Content-Type': 'application/json' },
        });
      }
    }

    const event = JSON.parse(rawBody);
    const eventType = event?.data?.attributes?.type;

    console.log('Webhook event received:', eventType);

    if (eventType !== 'checkout_session.payment.paid') {
      // Acknowledge events we don't handle
      return new Response(JSON.stringify({ received: true }), {
        status: 200,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // Extract checkout session data from the event
    const checkoutData = event.data.attributes.data;
    const checkoutId = checkoutData.id;
    const metadata = checkoutData.attributes?.metadata || {};
    const paymentId =
      checkoutData.attributes?.payments?.[0]?.id ||
      checkoutData.attributes?.payment_intent?.id ||
      '';

    const userId = metadata.user_id;
    const tier = metadata.tier;
    const validTiers = ['basic', 'plus', 'premium'];

    if (!userId || !tier || !validTiers.includes(tier)) {
      console.error('Missing metadata in webhook:', metadata);
      return new Response(JSON.stringify({ error: 'Missing metadata' }), {
        status: 400,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    const supabaseAdmin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    // Idempotency: check if payment already processed
    const { data: existingPayment } = await supabaseAdmin
      .from('payments')
      .select('status')
      .eq('paymongo_checkout_id', checkoutId)
      .single();

    if (existingPayment?.status === 'paid') {
      console.log('Payment already processed, skipping:', checkoutId);
      return new Response(JSON.stringify({ received: true, already_processed: true }), {
        status: 200,
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // Calculate expiry: 30 days from now
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 30);

    // Update user profile with new subscription tier
    const { error: profileError } = await supabaseAdmin
      .from('profiles')
      .update({
        subscription_tier: tier,
        subscription_status: 'active',
        subscription_expires_at: expiresAt.toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', userId);

    if (profileError) {
      console.error('Failed to update profile:', profileError);
      throw new Error(`Profile update failed: ${profileError.message}`);
    }

    // Update payment record
    const { error: paymentError } = await supabaseAdmin
      .from('payments')
      .update({
        status: 'paid',
        paymongo_payment_id: paymentId,
        updated_at: new Date().toISOString(),
      })
      .eq('paymongo_checkout_id', checkoutId);

    if (paymentError) {
      console.error('Failed to update payment:', paymentError);
      // Non-critical: profile is already updated
    }

    console.log(`Successfully upgraded user ${userId} to ${tier}`);

    return new Response(
      JSON.stringify({ received: true, user_id: userId, tier }),
      {
        status: 200,
        headers: { ...headers, 'Content-Type': 'application/json' },
      }
    );
  } catch (err) {
    console.error('paymongo-webhook error:', err);
    return new Response(
      JSON.stringify({ error: err.message || 'Internal server error' }),
      {
        status: 500,
        headers: { ...headers, 'Content-Type': 'application/json' },
      }
    );
  }
});
