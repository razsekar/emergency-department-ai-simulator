export interface NavItem {
  path: string;
  label: string;
  icon: string;
  /** Implementation phase in which this page becomes functional. */
  phase: number;
  summary: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { path: 'dashboard', label: 'Dashboard', icon: 'monitoring', phase: 3, summary: 'Operational metrics calculated from database records.' },
  { path: 'patient-queue', label: 'Patient Queue', icon: 'groups', phase: 3, summary: 'Synthetic patient visits with filters.' },
  { path: 'resources', label: 'Resource Management', icon: 'bed', phase: 3, summary: 'Staff, beds, departments and investigation facilities.' },
  { path: 'simulator', label: 'Scenario Simulator', icon: 'tune', phase: 3, summary: 'Load, edit and apply scenarios to the database.' },
  { path: 'knowledge-base', label: 'Knowledge Base', icon: 'menu_book', phase: 4, summary: 'Upload and search policy documents (RAG).' },
  { path: 'assistant', label: 'AI Assistant', icon: 'chat', phase: 5, summary: 'Chat with citations from retrieved policies.' },
  { path: 'agent', label: 'Agent Execution', icon: 'smart_toy', phase: 6, summary: 'Tool-calling agent runs and execution traces.' },
  { path: 'playground', label: 'Model Playground', icon: 'science', phase: 5, summary: 'Choose provider, model and parameters.' },
  { path: 'comparison', label: 'Response Comparison', icon: 'compare', phase: 8, summary: 'Same question, different data, side by side.' },
  { path: 'settings', label: 'Settings', icon: 'settings', phase: 5, summary: 'Provider configuration status (no secrets shown).' },
];
