import { defineRailway, github, postgres, preserve, project, redis, service, volume } from "railway/iac";

export default defineRailway(() => {
  const Redis = redis("Redis", { region: "iad" });
  Redis.deploy = { startCommand: "/bin/sh -c \"rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH\"" };
  Redis.networking = { privateNetworkEndpoint: "redis" };
  const Postgres = postgres("Postgres", { region: "iad" });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "iad", sizeMB: 5000 });
  const redisVolume = volume("redis-volume", { alerts: { usage: { "100": {}, "80": {}, "95": {} } }, allowOnlineResize: true, region: "iad", sizeMB: 5000 });
  const XepaySaaS = service("Xepay-SaaS", {
    source: github("Alasdia/Xepay-SaaS", { checkSuites: false }),
    start: "uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 2",
    replicas: { "iad": 4 },
    domains: ["api.alasdia.com"],
    networking: { privateNetworkEndpoint: "xepay-saas" },
    env: { DATABASE_URL: preserve(), GOOGLE_CLIENT_ID: preserve(), GOOGLE_CLIENT_SECRET: preserve(), GOOGLE_REDIRECT_URI: preserve(), OPENAI_API_KEY: preserve(), REDIS_URL: preserve(), RESEND_API_KEY: preserve(), SECRET_KEY: preserve(), STRIPE_SECRET_KEY: preserve(), STRIPE_WEBHOOK_SECRET_CONNECT: preserve(), STRIPE_WEBHOOK_SECRET_SUBSCRIPTION: preserve(), TWO_FACTOR_ENCRYPTION_KEY: preserve(), WEBHOOK_SECRET_PAYMENT: preserve() },
  });
  XepaySaaS.deploy = {
    healthcheckPath: "/health",
    healthcheckTimeout: 10,
  };

  const ExpirePlansCron = service("expire-plans-cron", {
    source: github("Alasdia/Xepay-SaaS", { checkSuites: false }),
    env: { DATABASE_URL: Postgres.env.DATABASE_URL },
  });
  ExpirePlansCron.deploy = {
    startCommand: "python -m backend.jobs.expire_plans",
    cronSchedule: "0 * * * *",
  };

  return project("successful-illumination", {
    resources: [XepaySaaS, Redis, Postgres, postgresVolume, redisVolume, ExpirePlansCron],
  });
});
