import { Routes } from '@angular/router';
import { NAV_ITEMS } from './core/nav-items';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  ...NAV_ITEMS.map((nav) => ({
    path: nav.path,
    title: `${nav.label} · ED Simulator`,
    data: { nav },
    // Lazy-loaded; real feature pages replace the stub in later phases.
    loadComponent: () => import('./shared/stub-page').then((m) => m.StubPage),
  })),
  { path: '**', redirectTo: 'dashboard' },
];
