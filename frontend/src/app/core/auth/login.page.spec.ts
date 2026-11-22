import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginPage, safeReturnUrl } from './login.page';

const user = { id: 'u', username: 'demo_viewer', display_name: 'V', roles: ['viewer'], permissions: [] };

describe('safeReturnUrl', () => {
  it('defaults to the Dashboard', () => {
    expect(safeReturnUrl(null)).toBe('/dashboard');
    expect(safeReturnUrl('')).toBe('/dashboard');
  });

  it('keeps the originally requested in-app URL', () => {
    expect(safeReturnUrl('/simulator')).toBe('/simulator');
    expect(safeReturnUrl('/patient-queue?status=waiting')).toBe('/patient-queue?status=waiting');
  });

  it('rejects open redirects and loops back to /login', () => {
    for (const bad of ['https://evil.example', '//evil.example', '/\\evil.example', 'javascript:alert(1)', '/login', '/login?returnUrl=%2Fx']) {
      expect(safeReturnUrl(bad), bad).toBe('/dashboard');
    }
  });
});

describe('LoginPage', () => {
  function setup(returnUrl: string | null) {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap(returnUrl ? { returnUrl } : {}) } } },
      ],
    });
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    return fixture;
  }

  it('lists the demo usernames but no passwords', () => {
    const el = setup(null).nativeElement as HTMLElement;
    const hint = el.querySelector('[data-test="login-hint"]')?.textContent ?? '';
    for (const name of ['demo_admin', 'demo_presenter', 'demo_viewer']) expect(hint).toContain(name);
    expect(hint.toLowerCase()).not.toMatch(/password\s*[:=]/);
  });

  async function signIn(returnUrl: string | null): Promise<string> {
    const fixture = setup(returnUrl);
    const nav = vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
    const el = fixture.nativeElement as HTMLElement;
    const set = (sel: string, v: string) => {
      const input = el.querySelector(sel) as HTMLInputElement;
      input.value = v;
      input.dispatchEvent(new Event('input'));
    };
    set('input[formControlName="username"]', 'demo_viewer');
    set('input[formControlName="password"]', 'x');
    fixture.detectChanges();
    (el.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    TestBed.inject(HttpTestingController)
      .expectOne('/api/auth/login')
      .flush({ access_token: 'abc', token_type: 'bearer', expires_in: 3600, user });
    return nav.mock.calls[0][0] as string;
  }

  it('after sign-in returns to the originally requested URL', async () => {
    expect(await signIn('/simulator')).toBe('/simulator');
  });

  it('after sign-in goes to the Dashboard when there was no requested URL', async () => {
    expect(await signIn(null)).toBe('/dashboard');
  });
});
