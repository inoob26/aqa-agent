# Scaffold for a project without Playwright

Apply this only after the person said "yes". Show the list of files and the install command
first. Do not overwrite a file that exists: merge into it, or ask.

## 1. Packages

Detect the package manager from the lock file (`pnpm-lock.yaml`, `yarn.lock`,
`package-lock.json`, `bun.lockb`). Without `package.json`, ask the person whether to create one.

```bash
npm i -D @playwright/test playwright-bdd typescript @types/node
npx playwright install --with-deps chromium
```

Add `playwright-bdd` only when the project uses `.feature` files (BDD mode).

## 2. playwright.config.ts

```ts
import { defineConfig, devices } from '@playwright/test';
import { defineBddConfig } from 'playwright-bdd';

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API_URL = process.env.API_URL ?? BASE_URL;

const bddApi = defineBddConfig({
  outputDir: '.features-gen/api',
  features: 'tests/features/**/*.feature',
  steps: ['tests/steps/api/**/*.ts', 'tests/fixtures/**/*.ts'],
  tags: '@api and not @manual',
});

const bddUi = defineBddConfig({
  outputDir: '.features-gen/ui',
  features: 'tests/features/**/*.feature',
  steps: ['tests/steps/ui/**/*.ts', 'tests/fixtures/**/*.ts'],
  tags: '@ui and not @manual',
});

export default defineConfig({
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: 'test-results/results.json' }]],
  use: { trace: 'on-first-retry' },
  projects: [
    { name: 'api', testDir: 'tests/api', use: { baseURL: API_URL } },
    { name: 'e2e', testDir: 'tests/e2e', use: { ...devices['Desktop Chrome'], baseURL: BASE_URL } },
    { name: 'bdd-api', testDir: bddApi, use: { baseURL: API_URL } },
    { name: 'bdd-ui', testDir: bddUi, use: { ...devices['Desktop Chrome'], baseURL: BASE_URL } },
  ],
});
```

Remove the BDD projects and the `playwright-bdd` import if the project has no `.feature` files.

## 3. Fixtures

`tests/fixtures/base.ts` — one `test` object for plain specs and for BDD steps:

```ts
import { test as base, createBdd } from 'playwright-bdd';
export { expect } from '@playwright/test';

type Fixtures = {
  // Add fixtures here: an authenticated API context, page objects, data factories.
};

export const test = base.extend<Fixtures>({});
export const { Given, When, Then } = createBdd(test);
```

In plain mode without `playwright-bdd`, import `test` from `@playwright/test` instead and
drop `createBdd`.

## 4. Other files

- `.gitignore`: add `test-results/`, `playwright-report/`, `.features-gen/`.
- `package.json` scripts:
  - `"test:api": "playwright test --project=api"`
  - `"test:e2e": "playwright test --project=e2e"`
  - `"test:bdd": "bddgen && playwright test --project=bdd-api --project=bdd-ui"`
- `tsconfig.json` if none exists: `"strict": true`, `"module": "commonjs"` or `"nodenext"`
  as the project uses, `"types": ["node"]`.
- `.env.example` with `BASE_URL`, `API_URL` and the names (not values) of the credential
  variables that the tests read.
