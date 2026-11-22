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
    expect(NAV_ITEMS.length).toBe(10);
    expect(el.querySelectorAll('mat-nav-list a').length).toBe(10);
    TestBed.inject(HttpTestingController).match(() => true);
  });
});
