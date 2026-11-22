import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';
import { routes } from './app.routes';
import { NAV_ITEMS } from './core/nav-items';

describe('App shell', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('shows the SIMULATION MODE banner and all 10 navigation items', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('SIMULATION MODE');
    expect(NAV_ITEMS.length).toBe(11); // the 10 original pages plus Demo Mode
    expect(el.querySelectorAll('nav.navlist a.nav-link').length).toBe(NAV_ITEMS.length);
    TestBed.inject(HttpTestingController).match(() => true);
  });

  it('keeps the toolbar on one row: three status chips in one group, names still readable by assistive tech', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const el: HTMLElement = fixture.nativeElement;
    const group = el.querySelector('.toolbar [role="group"][aria-label="System status"]');
    expect(group).not.toBeNull();
    const chips = [...(group as Element).querySelectorAll('.chip')];
    expect(chips.map((c) => c.querySelector('.chip-name')?.textContent)).toEqual(['Backend', 'Database', 'pgvector']);
    expect(chips.every((c) => (c.getAttribute('title') ?? '').includes(':'))).toBe(true);
    TestBed.inject(HttpTestingController).match(() => true);
  });
});
