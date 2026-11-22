import { Routes } from '@angular/router';
import { authGuard } from './core/auth/auth.guard';
import { NAV_ITEMS } from './core/nav-items';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  // --- F2 routes (first match wins over the stub map below) ---
  {
    path: 'login',
    title: 'Sign in · ED Simulator',
    loadComponent: () => import('./core/auth/login.page').then((m) => m.LoginPage),
  },
  {
    path: 'knowledge-base',
    title: 'Knowledge Base · ED Simulator',
    canActivate: [authGuard],
    loadComponent: () => import('./features/knowledge/knowledge.page').then((m) => m.KnowledgePage),
  },
  {
    path: 'assistant',
    title: 'AI Assistant · ED Simulator',
    canActivate: [authGuard],
    loadComponent: () => import('./features/assistant/assistant.page').then((m) => m.AssistantPage),
  },
  {
    path: 'playground',
    title: 'Model Playground · ED Simulator',
    canActivate: [authGuard],
    loadComponent: () => import('./features/playground/playground.page').then((m) => m.PlaygroundPage),
  },
  {
    path: 'settings',
    title: 'Settings · ED Simulator',
    canActivate: [authGuard],
    loadComponent: () => import('./features/settings/settings.page').then((m) => m.SettingsPage),
  },
  // --- end F2 routes ---
  // --- F1 routes: operations screens (backend endpoints are currently unauthenticated) ---
  {
    path: 'dashboard',
    title: 'Dashboard · ED Simulator',
    loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'patient-queue',
    title: 'Patient Queue · ED Simulator',
    loadComponent: () => import('./features/queue/queue.page').then((m) => m.QueuePage),
  },
  {
    path: 'resources',
    title: 'Resource Management · ED Simulator',
    loadComponent: () => import('./features/resources/resources.page').then((m) => m.ResourcesPage),
  },
  {
    path: 'simulator',
    title: 'Scenario Simulator · ED Simulator',
    loadComponent: () => import('./features/simulator/simulator.page').then((m) => m.SimulatorPage),
  },
  // --- end F1 routes ---
  // --- worker I routes ---
  {
    path: 'agent',
    title: 'Agent Execution · ED Simulator',
    loadComponent: () => import('./features/agent/agent.page').then((m) => m.AgentPage),
  },
  // --- end worker I routes ---
  // --- worker J routes: demo mode and model comparison (no guards: the backend enforces RBAC) ---
  {
    path: 'demo',
    title: 'Demo Mode · ED Simulator',
    loadComponent: () => import('./features/demo/demo.page').then((m) => m.DemoPage),
  },
  {
    path: 'comparison',
    title: 'Response Comparison · ED Simulator',
    loadComponent: () => import('./features/comparison/comparison.page').then((m) => m.ComparisonPage),
  },
  // --- end worker J routes ---
  ...NAV_ITEMS.map((nav) => ({
    path: nav.path,
    title: `${nav.label} · ED Simulator`,
    data: { nav },
    // Lazy-loaded; real feature pages replace the stub in later phases.
    loadComponent: () => import('./shared/stub-page').then((m) => m.StubPage),
  })),
  { path: '**', redirectTo: 'dashboard' },
];
