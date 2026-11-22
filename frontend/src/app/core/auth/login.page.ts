import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-login-page',
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-card appearance="outlined" class="login">
      <mat-card-header>
        <mat-icon mat-card-avatar>lock</mat-icon>
        <mat-card-title>Sign in</mat-card-title>
        <mat-card-subtitle>Demo accounts only. Synthetic data.</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="submit()" class="form">
          <mat-form-field appearance="outline">
            <mat-label>Username</mat-label>
            <input matInput formControlName="username" autocomplete="username" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Password</mat-label>
            <input matInput type="password" formControlName="password" autocomplete="current-password" />
          </mat-form-field>
          @if (error()) {
            <p class="error" role="alert">{{ error() }}</p>
          }
          <p class="hint" data-test="login-hint">
            Demo accounts: <strong>demo_admin</strong>, <strong>demo_presenter</strong>, <strong>demo_viewer</strong>.
            Passwords are set by the administrator in the server's <code>.env</code>.
          </p>
          <button mat-flat-button type="submit" [disabled]="form.invalid || busy()">
            {{ busy() ? 'Signing in…' : 'Sign in' }}
          </button>
        </form>
      </mat-card-content>
    </mat-card>
  `,
  styles: `
    .login { max-width: 420px; margin: 48px auto; }
    .form { display: flex; flex-direction: column; gap: 4px; padding-top: 16px; }
    .error { color: #b3261e; margin: 0 0 8px; }
    .hint { font-size: 13px; opacity: 0.8; margin: 0 0 12px; }
  `,
})
export class LoginPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly form = inject(FormBuilder).nonNullable.group({
    username: ['', [Validators.required, Validators.maxLength(64)]],
    password: ['', [Validators.required, Validators.maxLength(256)]],
  });

  protected submit(): void {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.error.set(null);
    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => {
        const target = this.route.snapshot.queryParamMap.get('returnUrl');
        void this.router.navigateByUrl(safeReturnUrl(target));
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(describeLoginError(err));
      },
    });
  }
}

/**
 * Where to go after sign-in: the originally requested in-app URL, otherwise the Dashboard.
 * Only in-app relative targets are accepted (prevents open redirects), and /login itself is never a target.
 */
export function safeReturnUrl(target: string | null): string {
  if (!target || !target.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) return '/dashboard';
  if (target === '/login' || target.startsWith('/login?') || target.startsWith('/login/')) return '/dashboard';
  return target;
}

export function describeLoginError(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    if (err.status === 401) return 'Invalid username or password.';
    if (err.status === 429) return 'Too many failed sign-in attempts. Wait a little and try again.';
    if (err.status === 500 && err.error?.error?.code === 'auth_not_configured') {
      return 'Authentication is not configured on the server (JWT_SECRET missing). Ask the administrator.';
    }
    if (err.status === 0) return 'Cannot reach the backend.';
  }
  return 'Sign-in failed. Please try again.';
}
