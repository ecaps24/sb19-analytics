const PAYMONGO_API = 'https://api.paymongo.com/v1';

interface CheckoutLineItem {
  name: string;
  amount: number; // centavos
  currency: string;
  quantity: number;
}

interface CreateCheckoutParams {
  lineItems: CheckoutLineItem[];
  description: string;
  metadata: Record<string, string>;
  successUrl: string;
  cancelUrl: string;
  paymentMethodTypes?: string[];
}

export async function createCheckoutSession(
  secretKey: string,
  params: CreateCheckoutParams
) {
  const body = {
    data: {
      attributes: {
        line_items: params.lineItems.map((item) => ({
          name: item.name,
          amount: item.amount,
          currency: item.currency,
          quantity: item.quantity,
        })),
        description: params.description,
        payment_method_types: params.paymentMethodTypes || [
          'gcash',
          'card',
          'paymaya',
          'grab_pay',
        ],
        success_url: params.successUrl,
        cancel_url: params.cancelUrl,
        metadata: params.metadata,
      },
    },
  };

  const resp = await fetch(`${PAYMONGO_API}/checkout_sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      Authorization: `Basic ${btoa(secretKey + ':')}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(
      `PayMongo API error ${resp.status}: ${JSON.stringify(err)}`
    );
  }

  return resp.json();
}

export async function retrieveCheckoutSession(
  secretKey: string,
  checkoutId: string
) {
  const resp = await fetch(`${PAYMONGO_API}/checkout_sessions/${checkoutId}`, {
    headers: {
      Accept: 'application/json',
      Authorization: `Basic ${btoa(secretKey + ':')}`,
    },
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(
      `PayMongo API error ${resp.status}: ${JSON.stringify(err)}`
    );
  }

  return resp.json();
}
