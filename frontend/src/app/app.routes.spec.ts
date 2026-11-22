import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Route, Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { routes } from './app.routes';
import { authGuard } from './core/auth/auth.guard';
import { NAV_ITEMS } from './core/nav-items';

/** Every route reachable below this one, with the chain of guards that protects it. */
function flatten(rs: Route[], inherited: unknown[] = []): { path: string; guards: unknown[] }[] {
  return rs.flatMap((r) => {
    const guards = [...inherited, ...(r.canActivate ?? []), ...(r.canActivateChild ?? [])];
    const here = r.component || r.loadComponent || r.redirectTo ? [{ path: r.path ?? '', guards }] : [];
    // canActivateChild on a parent protects its children
    const childGuards = [...inherited, ...(r.canActivate ?? []), ...(r.canActivateChild ?? [])];
    return [...here, ...(r.children ? flatten(r.children, childGuards) : [])];
  });
}

describe('route guarding', () => {
  it('/login is the only route without authGuard', () => {
    const unguarded = flatten(routes).filter((r) => !r.guards.includes(authGuard));
    expect(unguarded.map((r) => r.path)).toEqual(['login']);
  });

  it('every navigation item and the catch-all sit under the guarded parent', () => {
    const guarded = flatten(routes).filter((r) => r.guards.includes(authGuard)).map((r) => r.path);
    for (const nav of NAV_ITEMS) expect(guarded, nav.path).toContain(nav.path);
    expect(guarded).toContain('**');
    expect(guarded).toContain('demo');
    expect(guarded).toContain('comparison');
    expect(guarded).toContain('agent');
    expect(guarded).toContain('simulator');
  });
});

describe('anonymous navigation (real router)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  for (const url of ['/dashboard', '/simulator', '/demo', '/comparison', '/agent', '/knowledge-base', '/does-not-exist', '/']) {
    it(`redirects ${url} to /login with the requested URL`, async () => {
      const router = TestBed.inject(Router);
      await router.navigateByUrl(url);
      expect(router.url.startsWith('/login')).toBe(true);
      expect(router.url).toContain('returnUrl=');
    });
  }

  it('lets anonymous users open /login', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/login');
    expect(router.url).toBe('/login');
  });
});
