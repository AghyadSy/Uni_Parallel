import http from 'k6/http';
import exec from 'k6/execution';
import { check, fail } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const CONCURRENT_USERS = Number(__ENV.CONCURRENT_USERS || 100);
const PRODUCTS_REQUESTS = Number(__ENV.PRODUCTS_REQUESTS || 100);
const PRODUCTS_VUS = Number(__ENV.PRODUCTS_VUS || PRODUCTS_REQUESTS);
const MODE = __ENV.MODE || 'after';
const START_DELAY_MS = Number(__ENV.START_DELAY_MS || 0);
const PRODUCTS_START_OFFSET_MS = Number(__ENV.PRODUCTS_START_OFFSET_MS || 0);
const TEST_PROFILE = 'strict-fixed';
const USE_RESET_DATA = (__ENV.USE_RESET_DATA || 'false').trim().toLowerCase() === 'true';
const CUSTOMER_NAME_PREFIX = __ENV.CUSTOMER_NAME_PREFIX || 'k6-race-user';
const DEFAULT_API_URL = 'http://127.0.0.1:8000/api/demo/pessimistic-lock/batch/?requests=1&hold_seconds=1';
const DEFAULT_PRODUCTS_URL = 'http://127.0.0.1:8000/api/products/popular/';
const DEFAULT_RESET_URL = 'http://127.0.0.1:8000/api/demo/reset-data/';
const CHECKOUT_ERROR_THRESHOLD = Number(__ENV.CHECKOUT_ERROR_THRESHOLD || 0.01);
const PRODUCTS_ERROR_THRESHOLD = Number(__ENV.PRODUCTS_ERROR_THRESHOLD || 0.01);
const NETWORK_ERROR_THRESHOLD = Number(__ENV.NETWORK_ERROR_THRESHOLD || 0.01);
const CHECKOUT_P95_THRESHOLD_MS = Number(__ENV.CHECKOUT_P95_THRESHOLD_MS || 500);
const PRODUCTS_P95_THRESHOLD_MS = Number(__ENV.PRODUCTS_P95_THRESHOLD_MS || 500);

const apiUrl = normalizeUrl(__ENV.API_URL || DEFAULT_API_URL);
const productsUrl = normalizeUrl(__ENV.PRODUCTS_URL || DEFAULT_PRODUCTS_URL);
const resetUrl = normalizeUrl(__ENV.RESET_URL || DEFAULT_RESET_URL);

const checkoutLatency = new Trend('checkout_latency_ms', true);
const checkoutErrorRate = new Rate('checkout_error_rate');
const checkoutAcceptedStatusRate = new Rate('checkout_accepted_status_rate');
const checkoutRequestsTotal = new Counter('checkout_requests_total');
const checkoutStatus200Total = new Counter('checkout_status_200_total');
const checkoutStatus201Total = new Counter('checkout_status_201_total');
const checkoutStatus400Total = new Counter('checkout_status_400_total');
const checkoutStatus500Total = new Counter('checkout_status_500_total');
const checkoutUnexpectedStatusTotal = new Counter('checkout_unexpected_status_total');
const checkoutNetworkErrorsTotal = new Counter('checkout_network_errors_total');

const productsLatency = new Trend('products_latency_ms', true);
const productsErrorRate = new Rate('products_error_rate');
const productsAcceptedStatusRate = new Rate('products_accepted_status_rate');
const productsRequestsTotal = new Counter('products_requests_total');
const productsStatus200Total = new Counter('products_status_200_total');
const productsUnexpectedStatusTotal = new Counter('products_unexpected_status_total');
const productsNetworkErrorsTotal = new Counter('products_network_errors_total');

const networkErrorRate = new Rate('network_error_rate');
const networkErrorsTotal = new Counter('network_errors_total');
const connectionRefusedTotal = new Counter('connection_refused_total');
const timeoutErrorsTotal = new Counter('timeout_errors_total');
const resetErrorsTotal = new Counter('connection_reset_total');
const dnsErrorsTotal = new Counter('dns_errors_total');

export const options = {
  scenarios: buildScenarios(),
  thresholds: {
    checkout_error_rate: [`rate<${CHECKOUT_ERROR_THRESHOLD}`],
    checkout_latency_ms: [`p(95)<${CHECKOUT_P95_THRESHOLD_MS}`],
    products_error_rate: [`rate<${PRODUCTS_ERROR_THRESHOLD}`],
    products_latency_ms: [`p(95)<${PRODUCTS_P95_THRESHOLD_MS}`],
    network_error_rate: [`rate<${NETWORK_ERROR_THRESHOLD}`],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)'],
  userAgent: 'k6-checkout-performance/2.0',
};

export function setup() {
  if (CONCURRENT_USERS <= 0 || PRODUCTS_REQUESTS <= 0) {
    fail('CONCURRENT_USERS and PRODUCTS_REQUESTS must be greater than zero.');
  }

  if (PRODUCTS_VUS !== PRODUCTS_REQUESTS) {
    fail(
      `Strict fixed-load mode requires PRODUCTS_VUS (${PRODUCTS_VUS}) to equal PRODUCTS_REQUESTS (${PRODUCTS_REQUESTS}).`
    );
  }

  if (!USE_RESET_DATA) {
    return {};
  }

  const response = http.post(resetUrl, JSON.stringify({}), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'demo-reset-data' },
  });

  const setupOk = check(response, {
    'reset-data returned 200': (res) => res.status === 200,
  });

  if (!setupOk) {
    fail(
      `Failed to prepare test data via ${resetUrl}. Status=${response.status}, body=${response.body}`
    );
  }

  return {};
}

export function checkoutScenario() {
  const payload = JSON.stringify({
    request_label: `${CUSTOMER_NAME_PREFIX}-${exec.vu.idInTest}-${exec.scenario.iterationInTest}`,
  });

  const response = http.post(apiUrl, payload, {
    headers: { 'Content-Type': 'application/json' },
    tags: {
      endpoint: 'checkout',
      test_type: TEST_PROFILE,
    },
  });

  checkoutRequestsTotal.add(1);
  checkoutLatency.add(response.timings.duration);

  const allowedStatus = [200, 201, 400, 500].includes(response.status);
  const requestFailed = response.status === 0 || ![200, 201].includes(response.status);

  checkoutAcceptedStatusRate.add(allowedStatus);
  checkoutErrorRate.add(requestFailed);

  incrementCheckoutStatusCounter(response.status);
  recordNetworkFailure(response, 'checkout');

  check(response, {
    'status is 200, 201, 400, or 500': () => allowedStatus,
  });
}

export function productsScenario() {
  const response = http.get(withQueryParam(productsUrl, 'mode', MODE), {
    tags: {
      endpoint: 'products',
      test_type: TEST_PROFILE,
    },
  });

  productsRequestsTotal.add(1);
  productsLatency.add(response.timings.duration);

  const allowedStatus = response.status === 200;
  const requestFailed = response.status === 0 || !allowedStatus;

  productsAcceptedStatusRate.add(allowedStatus);
  productsErrorRate.add(requestFailed);

  if (response.status === 200) {
    productsStatus200Total.add(1);
  } else {
    productsUnexpectedStatusTotal.add(1);
  }

  recordNetworkFailure(response, 'products');

  check(response, {
    'products status is 200': (res) => res.status === 200,
  });
}

export function handleSummary(data) {
  const checkoutAvg = metricValue(data, 'checkout_latency_ms', 'avg');
  const checkoutP95 = metricValue(data, 'checkout_latency_ms', 'p(95)');
  const checkoutError = metricValue(data, 'checkout_error_rate', 'rate');
  const checkoutAccepted = metricValue(data, 'checkout_accepted_status_rate', 'rate');
  const checkoutTotal = metricValue(data, 'checkout_requests_total', 'count', 0);
  const checkout200 = metricValue(data, 'checkout_status_200_total', 'count', 0);
  const checkout201 = metricValue(data, 'checkout_status_201_total', 'count', 0);
  const checkout400 = metricValue(data, 'checkout_status_400_total', 'count', 0);
  const checkout500 = metricValue(data, 'checkout_status_500_total', 'count', 0);
  const checkoutUnexpected = metricValue(data, 'checkout_unexpected_status_total', 'count', 0);
  const checkoutNetwork = metricValue(data, 'checkout_network_errors_total', 'count', 0);

  const productsAvg = metricValue(data, 'products_latency_ms', 'avg');
  const productsP95 = metricValue(data, 'products_latency_ms', 'p(95)');
  const productsError = metricValue(data, 'products_error_rate', 'rate');
  const productsAccepted = metricValue(data, 'products_accepted_status_rate', 'rate');
  const productsTotal = metricValue(data, 'products_requests_total', 'count', 0);
  const products200 = metricValue(data, 'products_status_200_total', 'count', 0);
  const productsUnexpected = metricValue(data, 'products_unexpected_status_total', 'count', 0);
  const productsNetwork = metricValue(data, 'products_network_errors_total', 'count', 0);

  const totalThroughput = metricValue(data, 'http_reqs', 'rate');
  const totalNetworkErrorRate = metricValue(data, 'network_error_rate', 'rate');
  const totalNetworkErrors = metricValue(data, 'network_errors_total', 'count', 0);
  const refusedErrors = metricValue(data, 'connection_refused_total', 'count', 0);
  const timeoutErrors = metricValue(data, 'timeout_errors_total', 'count', 0);
  const resetErrors = metricValue(data, 'connection_reset_total', 'count', 0);
  const dnsErrors = metricValue(data, 'dns_errors_total', 'count', 0);

  const analysis = buildAnalysisHints({
    checkoutP95,
    productsP95,
    checkoutError,
    productsError,
    totalNetworkErrorRate,
    refusedErrors,
    timeoutErrors,
  });

  const lines = [
    '',
    '=== k6 Performance Summary ===',
    `Profile: ${TEST_PROFILE}`,
    `Checkout URL: ${apiUrl}`,
    `Products URL: ${withQueryParam(productsUrl, 'mode', MODE)}`,
    `Combined throughput: ${formatNumber(totalThroughput)} req/s`,
    `Network error rate: ${formatPercent(totalNetworkErrorRate)}`,
    `Network failures -> total: ${totalNetworkErrors}, refused: ${refusedErrors}, timeout: ${timeoutErrors}, reset: ${resetErrors}, dns: ${dnsErrors}`,
    '',
    '--- Checkout Scenario ---',
    `Configured users: ${CONCURRENT_USERS}`,
    `Total requests: ${checkoutTotal}`,
    `Latency avg: ${formatNumber(checkoutAvg)} ms`,
    `Latency p95: ${formatNumber(checkoutP95)} ms`,
    `Error rate: ${formatPercent(checkoutError)}`,
    `Accepted status rate: ${formatPercent(checkoutAccepted)}`,
    `Network errors: ${checkoutNetwork}`,
    `Status counts -> 200: ${checkout200}, 201: ${checkout201}, 400: ${checkout400}, 500: ${checkout500}, unexpected: ${checkoutUnexpected}`,
    '',
    '--- Products Scenario ---',
    `Configured requests: ${PRODUCTS_REQUESTS}`,
    `Configured VUs: ${PRODUCTS_VUS}`,
    `Start offset after checkout: ${PRODUCTS_START_OFFSET_MS} ms`,
    `Latency avg: ${formatNumber(productsAvg)} ms`,
    `Latency p95: ${formatNumber(productsP95)} ms`,
    `Error rate: ${formatPercent(productsError)}`,
    `Accepted status rate: ${formatPercent(productsAccepted)}`,
    `Network errors: ${productsNetwork}`,
    `Status counts -> 200: ${products200}, unexpected: ${productsUnexpected}`,
    '',
    '--- Analysis Hints ---',
    ...analysis.map((line) => `- ${line}`),
    '',
  ];

  return {
    stdout: `${lines.join('\n')}\n`,
    'k6-summary.json': JSON.stringify(data, null, 2),
  };
}

function buildScenarios() {
  return {
    simultaneous_checkout: {
      executor: 'per-vu-iterations',
      exec: 'checkoutScenario',
      vus: CONCURRENT_USERS,
      iterations: 1,
      startTime: `${START_DELAY_MS}ms`,
      maxDuration: '2m',
      gracefulStop: '0s',
    },
    products_browse: {
      executor: 'per-vu-iterations',
      exec: 'productsScenario',
      vus: PRODUCTS_VUS,
      iterations: 1,
      startTime: `${START_DELAY_MS + PRODUCTS_START_OFFSET_MS}ms`,
      maxDuration: '2m',
      gracefulStop: '0s',
    },
  };
}

function incrementCheckoutStatusCounter(status) {
  if (status === 200) {
    checkoutStatus200Total.add(1);
    return;
  }

  if (status === 201) {
    checkoutStatus201Total.add(1);
    return;
  }

  if (status === 400) {
    checkoutStatus400Total.add(1);
    return;
  }

  if (status === 500) {
    checkoutStatus500Total.add(1);
    return;
  }

  checkoutUnexpectedStatusTotal.add(1);
}

function recordNetworkFailure(response, scenarioName) {
  const isNetworkFailure = response.status === 0 || Boolean(response.error);
  networkErrorRate.add(isNetworkFailure);

  if (!isNetworkFailure) {
    return;
  }

  networkErrorsTotal.add(1);

  if (scenarioName === 'checkout') {
    checkoutNetworkErrorsTotal.add(1);
  } else {
    productsNetworkErrorsTotal.add(1);
  }

  const errorText = String(response.error || '').toLowerCase();

  if (errorText.includes('refused')) {
    connectionRefusedTotal.add(1);
    return;
  }

  if (errorText.includes('timeout') || errorText.includes('deadline')) {
    timeoutErrorsTotal.add(1);
    return;
  }

  if (errorText.includes('reset')) {
    resetErrorsTotal.add(1);
    return;
  }

  if (errorText.includes('dns') || errorText.includes('lookup')) {
    dnsErrorsTotal.add(1);
  }
}

function buildAnalysisHints(metrics) {
  const lines = [];

  if (metrics.refusedErrors > 0) {
    lines.push('Connection refused means requests are failing before the app returns HTTP. Focus on server workers, socket backlog, load balancer listener capacity, and process crashes.');
  }

  if (metrics.timeoutErrors > 0) {
    lines.push('Timeout failures indicate requests are queued too long or blocked on slow code paths such as DB locks, external calls, or synchronous post-checkout work.');
  }

  if (metrics.checkoutP95 > metrics.productsP95 * 1.5 && metrics.checkoutError >= metrics.productsError) {
    lines.push('Checkout is the primary bottleneck. Inspect transaction scope, row locks, stock update contention, and move post-payment work to queues.');
  }

  if (metrics.totalNetworkErrorRate >= 0.05) {
    lines.push('A large portion of failures happen at the runtime/network layer, so local dev servers are saturated before business logic executes.');
  }

  if (metrics.checkoutP95 > 2000 || metrics.productsP95 > 2000) {
    lines.push('p95 latency above 2s points to contention, not just slow handlers. Profile DB waits, connection acquisition, and thread/process exhaustion.');
  }

  if (lines.length === 0) {
    lines.push('No dominant bottleneck heuristic triggered. Inspect k6-summary.json together with backend logs, DB slow query logs, and server metrics.');
  }

  return lines;
}

function metricValue(data, metricName, field, fallback = NaN) {
  return data.metrics?.[metricName]?.values?.[field] ?? fallback;
}

function normalizeUrl(url) {
  const [baseUrl, query = ''] = String(url).split('?');
  const normalizedBaseUrl = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
  return query ? `${normalizedBaseUrl}?${query}` : normalizedBaseUrl;
}

function withQueryParam(url, key, value) {
  const encodedKey = encodeURIComponent(key);
  const encodedValue = encodeURIComponent(String(value));
  const matcher = new RegExp(`([?&])${encodedKey}=[^&]*`);

  if (matcher.test(url)) {
    return url.replace(matcher, `$1${encodedKey}=${encodedValue}`);
  }

  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${encodedKey}=${encodedValue}`;
}

function formatNumber(value) {
  if (!Number.isFinite(value)) {
    return 'n/a';
  }

  return value.toFixed(2);
}

function formatPercent(value) {
  if (!Number.isFinite(value)) {
    return 'n/a';
  }

  return `${(value * 100).toFixed(2)}%`;
}
