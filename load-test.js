import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.alasdia.com';
const TOKEN = __ENV.TOKEN;

const params = {
    headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: 'application/json',
    },
};

export const options = {
    stages: [
        { duration: '30s', target: 250 },
        { duration: '30s', target: 500 },
        { duration: '30s', target: 750 },
        { duration: '30s', target: 1000 },
        { duration: '1m', target: 1000 },
        { duration: '30s', target: 0 },
    ],
};

function get(path) {
    const res = http.get(`${BASE_URL}${path}`, params);

    check(res, {
        [`GET ${path} = 2xx`]: r =>
            r.status >= 200 && r.status < 300,
    });

    return res;
}

export default function () {

    get('/me');
    sleep(1);

    get('/me/plan');
    sleep(1);

    get('/me/user-plan');
    sleep(1);

    get('/stats');
    sleep(1);

    get('/wallet/history');
    sleep(1);

    get('/links/dashnoard');
    sleep(1);

    get('/links');
    sleep(1);

    get('/links');
    sleep(1);

    get('/wallet/me');
    sleep(1);

    get('/logs');
    sleep(1);

    get('/activity');

    sleep(2);
}