import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export interface BarDatum {
  label: string;
  value: number;
}

const W = 480;
const H = 220;
const PAD = { top: 22, right: 8, bottom: 40, left: 32 };

/** Dependency-free accessible SVG bar chart. Renders exactly the values it is given. */
@Component({
  selector: 'app-bar-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg [attr.viewBox]="'0 0 ' + w + ' ' + h" role="img" [attr.aria-label]="ariaLabel()" preserveAspectRatio="xMidYMid meet">
      <title>{{ ariaLabel() }}</title>
      @for (t of ticks(); track t.value) {
        <line [attr.x1]="pad.left" [attr.x2]="w - pad.right" [attr.y1]="t.y" [attr.y2]="t.y" class="grid" />
        <text [attr.x]="pad.left - 6" [attr.y]="t.y + 4" class="axis" text-anchor="end">{{ t.value }}</text>
      }
      @for (b of bars(); track $index) {
        <rect [attr.x]="b.x" [attr.y]="b.y" [attr.width]="b.w" [attr.height]="b.h" rx="2" [attr.fill]="color()">
          <title>{{ b.label }}: {{ b.value }}</title>
        </rect>
        <text [attr.x]="b.x + b.w / 2" [attr.y]="b.y - 4" class="value" text-anchor="middle">{{ b.value }}</text>
        <text [attr.x]="b.x + b.w / 2" [attr.y]="h - PAD_BOTTOM + 14" class="axis" text-anchor="middle">{{ b.label }}</text>
      }
      <line [attr.x1]="pad.left" [attr.x2]="w - pad.right" [attr.y1]="h - PAD_BOTTOM" [attr.y2]="h - PAD_BOTTOM" class="base" />
    </svg>
  `,
  styles: `
    :host { display: block; }
    svg { width: 100%; height: auto; display: block; }
    .grid { stroke: var(--mat-sys-outline-variant); stroke-width: 1; }
    .base { stroke: var(--mat-sys-outline); stroke-width: 1; }
    .axis { fill: var(--mat-sys-on-surface-variant); font-size: 11px; }
    .value { fill: var(--mat-sys-on-surface); font-size: 11px; font-weight: 500; }
  `,
})
export class BarChartComponent {
  readonly data = input.required<BarDatum[]>();
  readonly color = input('#0369a1');
  readonly ariaLabel = input('Bar chart');

  protected readonly w = W;
  protected readonly h = H;
  protected readonly pad = PAD;
  protected readonly PAD_BOTTOM = PAD.bottom;

  private readonly max = computed(() => {
    const m = Math.max(0, ...this.data().map((d) => d.value));
    return m === 0 ? 1 : m;
  });

  protected readonly ticks = computed(() => {
    const m = this.max();
    const plotH = H - PAD.top - PAD.bottom;
    return [0, 0.5, 1].map((f) => ({
      value: Math.round(m * f * 10) / 10,
      y: PAD.top + plotH - plotH * f,
    }));
  });

  protected readonly bars = computed(() => {
    const d = this.data();
    if (!d.length) return [];
    const plotW = W - PAD.left - PAD.right;
    const plotH = H - PAD.top - PAD.bottom;
    const slot = plotW / d.length;
    const bw = Math.min(48, slot * 0.7);
    return d.map((p, i) => {
      const h = (p.value / this.max()) * plotH;
      return {
        label: p.label,
        value: p.value,
        x: PAD.left + slot * i + (slot - bw) / 2,
        y: PAD.top + plotH - h,
        w: bw,
        h,
      };
    });
  });
}
