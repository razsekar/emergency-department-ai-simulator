import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';
import { AuthUser, LoginRequest, TokenResponse } from './auth.models';

const STORAGE_KEY = 'edsim.auth';

interface Stored {
  token: string;
  user: AuthUser;
  expiresAt: number;
}

/**
 * Holds the bearer token in memory and mirrors it to sessionStorage (cleared when the tab closes).
 * Storage access is always wrapped in try/catch: it can throw or be empty (private windows etc.).
 * The backend is the security boundary; permission checks here only drive what the UI shows.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  private readonly _token = signal<string | null>(null);
  private readonly _user = signal<AuthUser | null>(null);
  private expiresAt = 0;

  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._token() !== null && this._user() !== null);
  readonly roles = computed(() => this._user()?.roles ?? []);

  constructor() {
    this.restore();
  }

  token(): string | null {
    if (this._token() && Date.now() >= this.expiresAt) {
      this.logout();
    }
    return this._token();
  }

  login(credentials: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/api/auth/login', credentials).pipe(
      tap((res) => {
        this.expiresAt = Date.now() + res.expires_in * 1000;
        this._token.set(res.access_token);
        this._user.set(res.user);
        this.persist({ token: res.access_token, user: res.user, expiresAt: this.expiresAt });
      }),
    );
  }

  logout(): void {
    this._token.set(null);
    this._user.set(null);
    this.expiresAt = 0;
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable: nothing to clear */
    }
  }

  /** UX-only check. The server enforces every permission independently. */
  hasPermission(permission: string): boolean {
    return this._user()?.permissions.includes(permission) ?? false;
  }

  private persist(value: Stored): void {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } catch {
      /* keep working from memory only */
    }
  }

  private restore(): void {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const stored = JSON.parse(raw) as Partial<Stored>;
      if (stored.token && stored.user && typeof stored.expiresAt === 'number' && stored.expiresAt > Date.now()) {
        this.expiresAt = stored.expiresAt;
        this._token.set(stored.token);
        this._user.set(stored.user);
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      /* corrupt or unavailable storage: start logged out */
    }
  }
}
