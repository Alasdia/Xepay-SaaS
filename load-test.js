import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.alasdia.com';
const TOKEN = __ENV.TOKEN;

const params = {
    headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: 'application/json',
    },
    timeout: '30s',
};

export const options = {
    stages: [
        { duration: '30s', target: 100 },
        { duration: '30s', target: 250 },
        { duration: '30s', target: 500 },
        { duration: '1m', target: 500 },
        { duration: '30s', target: 0 },
    ],

    thresholds: {
        http_req_duration: ['p(95)<3000'],
    },
};

function get(path) {
    const res = http.get(`${BASE_URL}${path}`, params);

    check(res, {
        [`${path} → 2xx`]: r =>
            r.status >= 200 && r.status < 300,
    });

    // Affiche uniquement les erreurs
    if (res.status < 200 || res.status >= 300) {
        console.log(
            `❌ ${path} | HTTP ${res.status} | ${res.error || 'no error'}`
        );
    }

    return res;
}

export default function () {

    get('/me');
    get('/profile');
    get('/me/user-plan');
    get('/me/plan');

    get('/security/alerts');

    get('/workspaces/me');
    get('/users');
    get('/invites');

    get('/stripe/status');

    get('/wallet/me');
    get('/wallet/history');
    get('/wallet');

    get('/links');
    get('/links/dashboard');

    get('/activity');
    get('/logs');
    get('/logs/stats');

    get('/stats');

    get('/webhooks-api');

    get('/api-keys');

    get('/export/csv');
    get('/export/pdf');

    sleep(1);
}