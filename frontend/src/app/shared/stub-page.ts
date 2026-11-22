import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { ActivatedRoute } from '@angular/router';
import { NavItem } from '../core/nav-items';

/** Placeholder page shared by all not-yet-implemented features. Reads its content from route data. */
@Component({
  selector: 'app-stub-page',
  imports: [MatCardModule, MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <mat-card appearance="outlined">
      <mat-card-header>
        <mat-icon mat-card-avatar>{{ item.icon }}</mat-icon>
        <mat-card-title>{{ item.label }}</mat-card-title>
        <mat-card-subtitle>Coming in Phase {{ item.phase }}</mat-card-subtitle>
      </mat-card-header>
      <mat-card-content>
        <p>{{ item.summary }}</p>
      </mat-card-content>
    </mat-card>
  `,
  styles: `
    mat-card { max-width: 720px; }
    mat-card-content { padding-top: 16px; }
  `,
})
export class StubPage {
  protected readonly item = inject(ActivatedRoute).snapshot.data['nav'] as NavItem;
}
