/** Mirrors backend identity API schemas (backend/app/modules/identity/api/schemas.py). */
export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  roles: string[];
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface LoginRequest {
  username: string;
  password: string;
}

/** Permission names enforced by the backend. The frontend uses them for UX only (hide/disable). */
export const Permissions = {
  KnowledgeRead: 'knowledge:read',
  KnowledgeUpload: 'knowledge:upload',
  AiChat: 'ai:chat',
  ModelsRead: 'models:read',
  ModelsConfigure: 'models:configure',
} as const;
