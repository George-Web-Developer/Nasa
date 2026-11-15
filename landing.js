/**
 * Bio Astro Lab — Editorial Landing Controller (landing.js)
 * Hydrates real session telemetry (or honest NaN slots), runs Lenis Smooth Scroll
 * synchronized with GSAP ScrollTrigger for the right-to-left astronaut glide.
 */
(function (global) {
  'use strict';

  let gsapChoreographyDone = false;
  let lenisBound = false;

  function hydrateHeroTelemetry() {
    // Kept as hook for environment-change listeners without injecting artificial hero telemetry badges
  }

  function initAstronautChoreography() {
    if (global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    const gsap = global.gsap;
    const ScrollTrigger = global.ScrollTrigger;
    const Lenis = global.Lenis;
    if (!gsap || !ScrollTrigger) return;

    gsap.registerPlugin(ScrollTrigger);

    // Responsive smooth wheel inertial dampening synchronized 1:1 with ScrollTrigger (no double scrub lag)
    if (!lenisBound && typeof Lenis === 'function') {
      lenisBound = true;
      const lenis = new Lenis({
        lerp: 0.14,
        wheelMultiplier: 1.0,
        smoothWheel: true
      });
      lenis.on('scroll', ScrollTrigger.update);
      gsap.ticker.add((time) => lenis.raf(time * 1000));
      gsap.ticker.lagSmoothing(0);
    }

    if (gsapChoreographyDone) return;
    gsapChoreographyDone = true;

    const wrap = document.getElementById('heroAstronautWrap');
    const targetAnchor = document.getElementById('glideTargetAnchor');
    const heroStage = document.getElementById('heroStage');

    if (!wrap || !targetAnchor || !heroStage) return;

    const mm = gsap.matchMedia();
    mm.add('(min-width: 1025px)', () => {
      // Compute live translation vector relative to pristine (x=0, y=0) layout
      const measureDelta = () => {
        gsap.set(wrap, { x: 0, y: 0, scale: 1 });
        const fromRect = wrap.getBoundingClientRect();
        const toRect = targetAnchor.getBoundingClientRect();
        const targetX = toRect.left + toRect.width * 0.5 - (fromRect.left + fromRect.width * 0.5);
        const targetY = toRect.top + toRect.height * 0.5 - (fromRect.top + fromRect.height * 0.5) - 14;
        return { dx: targetX, dy: targetY };
      };

      let cached = measureDelta();

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: heroStage,
          start: 'top 62px',
          endTrigger: targetAnchor,
          end: 'center center',
          scrub: true,
          invalidateOnRefresh: true,
          onRefreshInit: () => {
            cached = measureDelta();
          }
        }
      });

      tl.to(
        wrap,
        {
          x: () => cached.dx,
          y: () => cached.dy,
          scale: 0.76,
          ease: 'none'
        },
        0
      );
    });

    const img = document.getElementById('heroAstronaut');
    if (img && !img.complete) {
      img.addEventListener('load', () => ScrollTrigger.refresh(), { once: true });
    }
  }

  function bootstrapLanding() {
    if (global.BioShell) {
      global.BioShell.renderShellChrome({ activeRoute: 'index.html', showFooter: true });
    }
    hydrateHeroTelemetry();
    document.addEventListener('bio:env-change', hydrateHeroTelemetry);
    initAstronautChoreography();
  }

  global.landingPage = {
    initMotion: initAstronautChoreography,
    hydrateHeroTelemetry
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapLanding);
  } else {
    bootstrapLanding();
  }
})(typeof window !== 'undefined' ? window : globalThis);
