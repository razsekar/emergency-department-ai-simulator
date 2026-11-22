import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

const user = { id: 'u', username: 'x', display_name: 'X', roles: ['viewer'], permissions: [] };

describe('authInterceptor', () => {
  let http: HttpClient;
  let ctrl: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpClient);
    ctrl = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  function signIn(): void {
    auth.login({ username: 'x', password: 'y' }).subscribe();
    ctrl.expectOne('/api/auth/login').flush({ access_token: 'abc', token_type: 'bearer', expires_in: 3600, user });
  }

  it('adds the bearer token to /api calls', () => {
    signIn();
    http.get('/api/health').subscribe();
    expect(ctrl.expectOne('/api/health').request.headers.get('Authorization')).toBe('Bearer abc');
  });

  it('does not attach the token to the login call or to non-API URLs', () => {
    signIn();
    http.post('/api/auth/login', {}).subscribe();
    expect(ctrl.expectOne('/api/auth/login').request.headers.has('Authorization')).toBe(false);
    http.get('https://example.com/x').subscribe();
    expect(ctrl.expectOne('https://example.com/x').request.headers.has('Authorization')).toBe(false);
  });

  it('signs out and redirects to /login on a 401 from the API', () => {
    signIn();
    const nav = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    http.get('/api/rag/search').subscribe({ error: () => undefined });
    ctrl.expectOne('/api/rag/search').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.isAuthenticated()).toBe(false);
    expect(nav).toHaveBeenCalledWith(['/login'], expect.anything());
  });

  it('does not sign out on a failed login (401 from the login call)', () => {
    signIn();
    http.post('/api/auth/login', {}).subscribe({ error: () => undefined });
    ctrl.expectOne('/api/auth/login').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.isAuthenticated()).toBe(true);
  });

  it('does not sign out on a 403', () => {
    signIn();
    http.get('/api/audit/events').subscribe({ error: () => undefined });
    ctrl.expectOne('/api/audit/events').flush({}, { status: 403, statusText: 'Forbidden' });
    expect(auth.isAuthenticated()).toBe(true);
  });
});
