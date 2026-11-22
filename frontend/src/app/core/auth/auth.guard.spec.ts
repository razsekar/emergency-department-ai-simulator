import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it } from 'vitest';
import { authGuard } from './auth.guard';
import { AuthService } from './auth.service';

const user = { id: 'u', username: 'x', display_name: 'X', roles: ['viewer'], permissions: [] };

describe('authGuard', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  });

  const run = () =>
    TestBed.runInInjectionContext(() => authGuard({} as ActivatedRouteSnapshot, { url: '/playground' } as RouterStateSnapshot));

  it('redirects anonymous users to /login with a returnUrl', () => {
    const result = run() as UrlTree;
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result)).toBe('/login?returnUrl=%2Fplayground');
  });

  it('allows signed-in users', () => {
    const auth = TestBed.inject(AuthService);
    auth.login({ username: 'x', password: 'y' }).subscribe();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/auth/login')
      .flush({ access_token: 'abc', token_type: 'bearer', expires_in: 3600, user });
    expect(run()).toBe(true);
  });
});
