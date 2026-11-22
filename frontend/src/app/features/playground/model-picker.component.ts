import { ChangeDetectionStrategy, Component, computed, effect, input, model } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { ModelInfo, ProviderName, ProviderStatus } from './providers.service';

/** Provider / model / temperature / streaming controls shared by the Playground and the Assistant. */
@Component({
  selector: 'app-model-picker',
  imports: [FormsModule, MatFormFieldModule, MatSelectModule, MatSliderModule, MatSlideToggleModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="row">
      <mat-form-field appearance="outline">
        <mat-label>Provider</mat-label>
        <mat-select [ngModel]="provider()" (ngModelChange)="provider.set($event)">
          @for (s of statuses(); track s.provider) {
            <mat-option [value]="s.provider">
              {{ s.label }} {{ s.configured ? '' : '(not configured)' }}
            </mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Model</mat-label>
        <mat-select [ngModel]="modelId()" (ngModelChange)="modelId.set($event)" [disabled]="providerModels().length === 0">
          @for (m of providerModels(); track m.model_id) {
            <mat-option [value]="m.model_id">{{ m.display_name }}</mat-option>
          }
        </mat-select>
        @if (providerModels().length === 0) {
          <mat-hint>No models listed for this provider.</mat-hint>
        }
      </mat-form-field>
    </div>

    <div class="row">
      <label class="temp">
        Temperature: <strong>{{ temperature().toFixed(1) }}</strong>
        <mat-slider min="0" max="2" step="0.1" discrete>
          <input matSliderThumb [ngModel]="temperature()" (ngModelChange)="temperature.set($event)" />
        </mat-slider>
      </label>
      <mat-slide-toggle [ngModel]="streaming()" (ngModelChange)="streaming.set($event)">Stream response</mat-slide-toggle>
    </div>
  `,
  styles: `
    .row { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
    mat-form-field { min-width: 220px; flex: 1 1 220px; }
    .temp { display: flex; align-items: center; gap: 8px; font-size: 14px; }
  `,
})
export class ModelPicker {
  readonly statuses = input.required<ProviderStatus[]>();
  readonly models = input.required<ModelInfo[]>();

  readonly provider = model<ProviderName | null>(null);
  readonly modelId = model<string | null>(null);
  readonly temperature = model(0.2);
  readonly streaming = model(true);

  protected readonly providerModels = computed(() => this.models().filter((m) => m.provider === this.provider()));

  constructor() {
    // Pick a sensible default provider (first configured) once statuses arrive.
    effect(() => {
      const statuses = this.statuses();
      if (!this.provider() && statuses.length) {
        this.provider.set((statuses.find((s) => s.configured) ?? statuses[0]).provider);
      }
    });
    // Keep the selected model valid for the chosen provider.
    effect(() => {
      const list = this.providerModels();
      const current = this.modelId();
      if (!list.some((m) => m.model_id === current)) this.modelId.set(list[0]?.model_id ?? null);
    });
  }
}
