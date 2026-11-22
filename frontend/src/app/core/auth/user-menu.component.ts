import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from './auth.service';

/** Toolbar widget: current user and roles, sign out / sign in. */
@Component({
  selector: 'app-user-menu',
  imports: [MatButtonModule, MatIconModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (auth.user(); as user) {
      <span class="who" [title]="user.permissions.join(', ')">
        <mat-icon aria-hidden="true">person</mat-icon>
        <span class="name">{{ user.display_name }}</span>
        <span class="roles">{{ user.roles.join(', ') }}</span>
      </span>
      <button mat-button type="button" (click)="signOut()">Sign out</button>
    } @else {
      <a mat-button routerLink="/login">Sign in</a>
    }
  `,
  styles: `
    :host { display: inline-flex; align-items: center; gap: 8px; margin-left: 12px; }
    .who { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; }
    .roles { opacity: 0.7; font-size: 12px; }
    @media (max-width: 700px) { .name, .roles { display: none; } }
  `,
})
export class UserMenu {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected signOut(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
