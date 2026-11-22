import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

/** Shown whenever the selected provider is a cloud service that will receive prompts. */
@Component({
  selector: 'app-cloud-disclosure',
  imports: [MatIconModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (cloud()) {
      <div class="disclosure" role="note">
        <mat-icon aria-hidden="true">cloud_upload</mat-icon>
        <span>
          <strong>Cloud provider:</strong>
          {{ text() || 'Your prompt and any document context are sent to this provider.' }}
        </span>
      </div>
    }
  `,
  styles: `
    .disclosure { display: flex; gap: 8px; align-items: center; padding: 8px 12px; border-radius: 8px;
      background: #fff4e0; color: #5b3b00; border: 1px solid #f0c36d; font-size: 13px; margin-bottom: 12px; }
  `,
})
export class CloudDisclosure {
  readonly cloud = input(false);
  readonly text = input<string | null>(null);
}
