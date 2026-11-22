import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { BreakpointObserver } from '@angular/cdk/layout';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map, switchMap, timer } from 'rxjs';
import { HealthService, ServiceState, UNKNOWN_HEALTH } from './core/health.service';
import { NAV_ITEMS } from './core/nav-items';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatChipsModule,
    MatButtonModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly health = inject(HealthService);

  protected readonly navItems = NAV_ITEMS;
  protected readonly isMobile = toSignal(
    inject(BreakpointObserver)
      .observe('(max-width: 900px)')
      .pipe(map((r) => r.matches)),
    { initialValue: false },
  );
  /** Polls backend health every 15 s. */
  protected readonly status = toSignal(timer(0, 15000).pipe(switchMap(() => this.health.check())), {
    initialValue: UNKNOWN_HEALTH,
  });

  protected label(state: ServiceState): string {
    return state === 'up' ? 'OK' : state === 'down' ? 'DOWN' : '—';
  }
}
