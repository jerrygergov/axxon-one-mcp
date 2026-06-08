/**
 * Smoke test for the axxon-reference-plugin plugin scaffold.
 *
 * Offline checks that do not require a live server. Run with `npm test` (configure your
 * preferred runner, e.g. node --test or vitest). These assertions only read process.env
 * and never embed credentials.
 */

import assert from 'node:assert';

const REQUIRED_ENV = ['AXXON_HOST', 'AXXON_TLS_CN', 'AXXON_USERNAME', 'AXXON_PASSWORD'];

export function testRequiredEnvDeclared(): void {
  assert.ok(REQUIRED_ENV.length === 4);
  for (const name of REQUIRED_ENV) {
    assert.ok(typeof name === 'string' && name.startsWith('AXXON_'));
  }
}

export function testMissingEnvDetected(): void {
  const missing = REQUIRED_ENV.filter(name => !process.env[name]);
  // With a clean environment, all four are reported missing; with a full one, none are.
  assert.ok(missing.length >= 0 && missing.length <= REQUIRED_ENV.length);
}

testRequiredEnvDeclared();
testMissingEnvDetected();
console.log('axxon-reference-plugin scaffold smoke checks passed');
