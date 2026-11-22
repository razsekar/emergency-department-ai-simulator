import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthUser, TokenResponse } from './auth.models';
import { AuthService } from './auth.service';

const user: AuthUser = {
  id: 'u1',
  username: 'demo_presenter',
  display_name: 'Demo Presenter',
  roles: ['presenter'],
  permissions: ['knowledge:read', 'ai:chat'],
};
const tokenResponse: TokenResponse = { access_token: 'tok', token_type: 'bearer', expires_in: 3600, user };

function setup(): { auth: AuthService; http: HttpTestingController } {
  TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
  return { auth: TestBed.inject(AuthService), http: TestBed.inject(HttpTestingController) };
}

describe('AuthService', () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it('logs in, exposes the user and persists to sessionStorage', () => {
    const { auth, http } = setup();
    auth.login({ username: 'demo_presenter', password: 'x' }).subscribe();
    const req = http.expectOne('/api/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ username: 'demo_presenter', password: 'x' });
    req.flush(tokenResponse);

    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.token()).toBe('tok');
    expect(auth.user()?.display_name).toBe('Demo Presenter');
    expect(auth.hasPermission('ai:chat')).toBe(true);
    expect(auth.hasPermission('models:configure')).toBe(false);
    expect(sessionStorage.getItem('edsim.auth')).toContain('tok');
  });

  it('logout clears state and storage', () => {
    const { auth, http } = setup();
    auth.login({ username: 'a', password: 'b' }).subscribe();
    http.expectOne('/api/auth/login').flush(tokenResponse);
    auth.logout();
    expect(auth.isAuthenticated()).toBe(false);
    expect(auth.token()).toBeNull();
    expect(sessionStorage.getItem('edsim.auth')).toBeNull();
  });

  it('restores a valid session from sessionStorage', () => {
    sessionStorage.setItem('edsim.auth', JSON.stringify({ token: 't2', user, expiresAt: Date.now() + 60_000 }));
    const { auth } = setup();
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.token()).toBe('t2');
  });

  it('ignores an expired stored session', () => {
    sessionStorage.setItem('edsim.auth', JSON.stringify({ token: 't3', user, expiresAt: Date.now() - 1 }));
    const { auth } = setup();
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('ignores corrupt storage', () => {
    sessionStorage.setItem('edsim.auth', '{not json');
    const { auth } = setup();
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('still works from memory when storage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    const { auth, http } = setup();
    auth.login({ username: 'a', password: 'b' }).subscribe();
    http.expectOne('/api/auth/login').flush(tokenResponse);
    expect(auth.isAuthenticated()).toBe(true);
  });

  it('treats a token past its expiry as logged out', () => {
    const { auth, http } = setup();
    auth.login({ username: 'a', password: 'b' }).subscribe();
    http.expectOne('/api/auth/login').flush({ ...tokenResponse, expires_in: -1 });
    expect(auth.token()).toBeNull();
    expect(auth.isAuthenticated()).toBe(false);
  });
});
