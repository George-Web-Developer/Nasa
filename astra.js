/**
 * Bio Astro Lab — ASTRA Daily Muscle Missions (astra.js)
 * NASA Space Apps 2026 — Astronaut Microgravity Musculoskeletal Countermeasure System
 * Strictly Rule-Based / LocalStorage Persistent / No AI
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'bioAstroLab.astra.v1';

  // Master 7-day schedule according to NASA flight medicine exercise protocols
  const ASTRA_SCHEDULE_DATA = [
    {
      dayNum: 1,
      title: 'Day 1: Full Body Microgravity Conditioning',
      focus: 'Full Body Training',
      subtitle: 'Countermeasures to combat extensor atrophy (soleus, quadriceps) and spinal decompression in orbit.',
      quote: 'High-load ARED resistance preserves bone mineral density and prevents sarcomere shortening.',
      tasks: [
        {
          id: 'd1_t1',
          name: 'ARED Barbell Squat',
          category: 'Lower Body',
          subgroup: 'Quadriceps & Glutes',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '4 sets × 10 reps @ 70% 1RM',
          instructions: 'Maintain heels firmly planted on the vibration isolation platform. Keep continuous spinal neutral alignment.'
        },
        {
          id: 'd1_t2',
          name: 'ARED Bench Press',
          category: 'Upper Body – Push',
          subgroup: 'Chest, Shoulders & Triceps',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps @ 65% 1RM',
          instructions: 'Lock shoulder blades against the bench pad. Control eccentric return phase against inertial flywheel canisters.'
        },
        {
          id: 'd1_t3',
          name: 'ARED Bent-Over Row',
          category: 'Upper Body – Pull',
          subgroup: 'Latissimus Dorsi & Biceps',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps @ 65% 1RM',
          instructions: 'Hinge at the hips with 45° torso angle. Pull elbows back firmly to engage upper postural stabilizers.'
        },
        {
          id: 'd1_t4',
          name: 'Core Spinal Stabilizer Planks',
          category: 'Core',
          subgroup: 'Abdominals & Erector Spinae',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '3 sets × 60s timed holds',
          instructions: 'Anchor feet in foot loops. Engage transverse abdominis to prevent lumbar hyper-extension.'
        },
        {
          id: 'd1_t5',
          name: 'T2 Treadmill Interval Run',
          category: 'Additional Training',
          subgroup: 'Cardiovascular Endurance',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'T2 Treadmill',
          equipClass: 't2',
          prescription: '5m warm-up + 4× (3m fast @ 80% HRmax / 2m jog)',
          instructions: 'Ensure bungee load-bearing harness is tightened to 75% bodyweight equivalent to stimulate heel impact.'
        }
      ]
    },
    {
      dayNum: 2,
      title: 'Day 2: Resistance & Aerobic Metabolic Loading',
      focus: 'Resistance & Aerobic',
      subtitle: 'Targeting posterior chain strength and cardiopulmonary stroke volume preservation.',
      quote: 'Aerobic intervals on CEVIS stimulate cardiac output and mitigate orthostatic intolerance upon return.',
      tasks: [
        {
          id: 'd2_t1',
          name: 'ARED Romanian Deadlift (RDL)',
          category: 'Lower Body',
          subgroup: 'Hamstrings & Posterior Chain',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '4 sets × 8 reps @ 75% 1RM',
          instructions: 'Push hips back with a slight knee bend. Emphasize eccentric hamstring stretch and glute contraction at top.'
        },
        {
          id: 'd2_t2',
          name: 'ARED Overhead Shoulder Press',
          category: 'Upper Body – Push',
          subgroup: 'Deltoids & Triceps',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps @ 60% 1RM',
          instructions: 'Press overhead from clavicle level without overarching the lumbar spine. Full lockout at top.'
        },
        {
          id: 'd2_t3',
          name: 'CEVIS High-Intensity Interval Training',
          category: 'Additional Training',
          subgroup: 'Cardiovascular Endurance',
          duration: '30 min',
          durationMinutes: 30,
          equipment: 'CEVIS Ergometer',
          equipClass: 'cevis',
          prescription: '12× (30s sprint @ >85% HRmax / 30s recovery spin)',
          instructions: 'Fasten toe clips tightly. Maintain cadence between 85–100 RPM during sprint intervals.'
        },
        {
          id: 'd2_t4',
          name: 'Hanging Knee / Leg Raises',
          category: 'Core',
          subgroup: 'Lower Abdominals & Hip Flexors',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'ARED Bar',
          equipClass: 'ared',
          prescription: '3 sets × 12 reps',
          instructions: 'Hold overhead bar with zero-G grip restraint. Flex knees toward chest without swinging.'
        }
      ]
    },
    {
      dayNum: 3,
      title: 'Day 3: Full Body Strength & Joint Armor',
      focus: 'Full Body Training',
      subtitle: 'Intensive calf and ankle tendon reinforcement to counteract calf volume loss (chicken leg syndrome).',
      quote: 'Calf muscle volume loss is rapid in microgravity; dedicated ARED heel raises are non-negotiable.',
      tasks: [
        {
          id: 'd3_t1',
          name: 'ARED Standing Calf / Heel Raises',
          category: 'Lower Body',
          subgroup: 'Soleus & Gastrocnemius',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '4 sets × 15 reps @ 80% 1RM',
          instructions: 'Full plantar flexion at top with 2-second hold to maximize soleus motor-unit recruitment.'
        },
        {
          id: 'd3_t2',
          name: 'ARED Upright Row & Biceps Curl',
          category: 'Upper Body – Pull',
          subgroup: 'Biceps & Trapezius',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 12 reps @ 65% 1RM',
          instructions: 'Control elbow flexion against continuous vacuum piston resistance. Avoid jerking motion.'
        },
        {
          id: 'd3_t3',
          name: 'ARED Incline Chest Push-Ups',
          category: 'Upper Body – Push',
          subgroup: 'Pectoralis Major & Serratus',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'ARED Bench',
          equipClass: 'ared',
          prescription: '3 sets × 12 reps',
          instructions: 'Keep body in a rigid plank. Push through palms to engage serratus anterior and shoulder girdle.'
        },
        {
          id: 'd3_t4',
          name: 'T2 Steady-State Aerobic Run',
          category: 'Additional Training',
          subgroup: 'Cardiovascular Endurance',
          duration: '30 min',
          durationMinutes: 30,
          equipment: 'T2 Treadmill',
          equipClass: 't2',
          prescription: '30 min sustained @ 70% HRmax (7.5 km/h)',
          instructions: 'Focus on symmetrical foot strike cadence to minimize microgravity gait deviation.'
        },
        {
          id: 'd3_t5',
          name: 'Pallof Press Anti-Rotation Holds',
          category: 'Core',
          subgroup: 'Obliques & Back Stabilizers',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Elastic Bands',
          equipClass: 'other',
          prescription: '3 sets × 10 reps per side (3s hold)',
          instructions: 'Resist rotational torque from elastic tether. Keep hips and shoulders perpendicular.'
        }
      ]
    },
    {
      dayNum: 4,
      title: 'Day 4: Active Recovery & Spinal Mobility',
      focus: 'Recovery & Mobility',
      subtitle: 'Restorative session to unload intervertebral discs and alleviate spaceflight back pain.',
      quote: 'Active recovery promotes circulatory flushing without accumulating neuromotor fatigue.',
      tasks: [
        {
          id: 'd4_t1',
          name: 'Spinal Decompression & Pelvic Tilts',
          category: 'Additional Training',
          subgroup: 'Mobility & Flexibility',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '4 rounds × 90s controlled flow',
          instructions: 'Gentle spinal flexion and extension (cat-cow) to relieve hyper-expanded lumbar vertebrae.'
        },
        {
          id: 'd4_t2',
          name: 'Hip & Lower Extremity Foam Rolling',
          category: 'Additional Training',
          subgroup: 'Mobility & Flexibility',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'Foam Roller / Mat',
          equipClass: 'other',
          prescription: 'Release IT band, quads, and glutes (2m per side)',
          instructions: 'Controlled myofascial pressure to increase local microvascular perfusion.'
        },
        {
          id: 'd4_t3',
          name: 'CEVIS Low-Resistance Aerobic Flush',
          category: 'Additional Training',
          subgroup: 'Recovery Activities',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'CEVIS Ergometer',
          equipClass: 'cevis',
          prescription: '25 min @ 45% VO2 peak (easy spinning 70 RPM)',
          instructions: 'Low intensity solely intended for lactic acid clearance and limb blood redistribution.'
        },
        {
          id: 'd4_t4',
          name: 'Scapular Retraction & Band Pull-Aparts',
          category: 'Upper Body – Pull',
          subgroup: 'Upper Postural Chain',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Elastic Bands',
          equipClass: 'other',
          prescription: '3 sets × 15 reps',
          instructions: 'Pinch shoulder blades together; counteract the natural zero-G neutral body posture curve.'
        }
      ]
    },
    {
      dayNum: 5,
      title: 'Day 5: Unilateral Strength & Core Armor',
      focus: 'Full Body Training',
      subtitle: 'Unilateral limb loading to correct left-right strength asymmetries developed in orbit.',
      quote: 'Unilateral loading challenges rotational stability and ensures equal bilateral bone density.',
      tasks: [
        {
          id: 'd5_t1',
          name: 'ARED Single-Leg Split Squat',
          category: 'Lower Body',
          subgroup: 'Quadriceps & Stabilizers',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 8 reps per leg @ 60% 1RM',
          instructions: 'Rear foot elevated on step. Lower slowly until front thigh is parallel to footplate.'
        },
        {
          id: 'd5_t2',
          name: 'ARED Close-Grip Incline Press',
          category: 'Upper Body – Push',
          subgroup: 'Triceps & Upper Chest',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps @ 65% 1RM',
          instructions: 'Keep elbows tucked within 30° of torso to direct force into triceps and anterior deltoids.'
        },
        {
          id: 'd5_t3',
          name: 'ARED Single-Arm Cable Row',
          category: 'Upper Body – Pull',
          subgroup: 'Rhomboids & Latissimus',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps per arm @ 60% 1RM',
          instructions: 'Pull cable handle to lower ribs while stabilizing torso against rotational tilt.'
        },
        {
          id: 'd5_t4',
          name: 'Quadruped Bird-Dog Core Extensions',
          category: 'Core',
          subgroup: 'Back Stabilizers & Glutes',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '3 sets × 10 reps per side (3s hold)',
          instructions: 'Simultaneously extend opposite arm and leg horizontally. Keep hips square and level.'
        },
        {
          id: 'd5_t5',
          name: 'T2 Variable-Speed Fartlek Run',
          category: 'Additional Training',
          subgroup: 'Cardiovascular Endurance',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'T2 Treadmill',
          equipClass: 't2',
          prescription: '6× (2m tempo pace / 1m recovery walk)',
          instructions: 'Harness load set to 70% equivalent. Replicate varied terrain locomotion mechanics.'
        }
      ]
    },
    {
      dayNum: 6,
      title: 'Day 6: Maximum Posterior Loading & VO2 Capacity',
      focus: 'Resistance & Aerobic',
      subtitle: 'High-power session to reinforce lumbar spine bone density and maximum oxygen consumption.',
      quote: 'Deadlifts are the ultimate defense against microgravity osteopenia in the hip and femoral neck.',
      tasks: [
        {
          id: 'd6_t1',
          name: 'ARED Heavy Deadlift',
          category: 'Lower Body',
          subgroup: 'Glutes, Hamstrings & Lumbar',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '4 sets × 8 reps @ 75% 1RM',
          instructions: 'Bar starts mid-shin. Drive through heel plates, locking hips and shoulders simultaneously.'
        },
        {
          id: 'd6_t2',
          name: 'ARED Push Press & Lateral Deltoid',
          category: 'Upper Body – Push',
          subgroup: 'Shoulders & Upper Chest',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'ARED',
          equipClass: 'ared',
          prescription: '3 sets × 10 reps @ 65% 1RM',
          instructions: 'Use slight leg drive to initiate bar velocity overhead. Lower with deliberate control.'
        },
        {
          id: 'd6_t3',
          name: 'CEVIS Sustained Aerobic Tempo (VO2)',
          category: 'Additional Training',
          subgroup: 'Cardiovascular Endurance',
          duration: '35 min',
          durationMinutes: 35,
          equipment: 'CEVIS Ergometer',
          equipClass: 'cevis',
          prescription: '35 min continuous @ 75% VO2 peak',
          instructions: 'Maintain cadence between 80–90 RPM. Hydrate every 10 minutes.'
        },
        {
          id: 'd6_t4',
          name: 'Russian Twists & Hollow Body Holds',
          category: 'Core',
          subgroup: 'Obliques & Transverse Abdominis',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '3 sets × 20 twists + 30s hollow hold',
          instructions: 'Keep feet anchored in restraints. Rotate ribcage through 45° while maintaining braced core.'
        }
      ]
    },
    {
      dayNum: 7,
      title: 'Day 7: Mission Reset & Neuromotor Recovery',
      focus: 'Recovery & Mobility',
      subtitle: 'Complete physical down-regulation and muscle tissue rehydration before the next weekly cycle.',
      quote: 'Recovery is where adaptation happens. Pushing through severe fatigue compromises mission safety.',
      tasks: [
        {
          id: 'd7_t1',
          name: 'Whole-Body Dynamic Flow & Joint Circles',
          category: 'Additional Training',
          subgroup: 'Mobility & Flexibility',
          duration: '25 min',
          durationMinutes: 25,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '3 rounds × full joint mobility circuit',
          instructions: 'Gentle ankle circles, wrist flexions, neck rotations, and thoracic windmills.'
        },
        {
          id: 'd7_t2',
          name: 'Diaphragmatic Breathing & Core Reset',
          category: 'Additional Training',
          subgroup: 'Recovery Activities',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'Mat / Restraints',
          equipClass: 'other',
          prescription: '15 min continuous focused belly breathing',
          instructions: 'Slow 4-second inhalation, 6-second exhalation to activate vagal parasympathetic recovery tone.'
        },
        {
          id: 'd7_t3',
          name: 'CEVIS Zero-Load Active Spinning',
          category: 'Additional Training',
          subgroup: 'Recovery Activities',
          duration: '20 min',
          durationMinutes: 20,
          equipment: 'CEVIS Ergometer',
          equipClass: 'cevis',
          prescription: '20 min @ minimal load (60 RPM)',
          instructions: 'Gentle spin solely to stimulate lower limb venous return without cardiovascular strain.'
        },
        {
          id: 'd7_t4',
          name: 'Hamstring & Achilles Restorative Stretch',
          category: 'Lower Body',
          subgroup: 'Hamstrings & Calves',
          duration: '15 min',
          durationMinutes: 15,
          equipment: 'Elastic Bands',
          equipClass: 'other',
          prescription: 'Hold each stretch 45–60s × 3 sets',
          instructions: 'Gentle static stretch using strap or band loop. Do not bounce or force painful range.'
        }
      ]
    }
  ];

  // Definition of gamification badges
  const MASTER_BADGES = [
    {
      id: 'full_body_anchor',
      icon: '🏋️',
      title: 'Full-Body Anchor',
      desc: 'Completed all prescribed tasks on a Full-Body training day.',
      check: (state) => {
        // Day 1, 3, or 5 is 100% complete
        return [1, 3, 5].some(d => getDayCompletionPct(state, d) === 100);
      }
    },
    {
      id: 'cardio_orbit',
      icon: '🚀',
      title: 'Cardio Orbit Master',
      desc: 'Completed T2 and CEVIS cardiovascular missions.',
      check: (state) => {
        return !!state.completed['d1_t5'] && !!state.completed['d2_t3'];
      }
    },
    {
      id: 'bone_defender',
      icon: '🦴',
      title: 'Bone Mineral Defender',
      desc: 'Executed heavy ARED Squat and Deadlift protocols.',
      check: (state) => {
        return !!state.completed['d1_t1'] && !!state.completed['d6_t1'];
      }
    },
    {
      id: 'mobility_master',
      icon: '🧘',
      title: 'Mobility Specialist',
      desc: 'Finished active recovery and spinal mobility sessions.',
      check: (state) => {
        return getDayCompletionPct(state, 4) >= 75 || getDayCompletionPct(state, 7) >= 75;
      }
    },
    {
      id: 'streak_champion',
      icon: '🔥',
      title: '14-Day Streak Pilot',
      desc: 'Maintained 14+ days consecutive exercise compliance.',
      check: (state) => (state.streakDays || 14) >= 14
    },
    {
      id: 'mission_specialist',
      icon: '🎖️',
      title: 'NASA Flight Compliant',
      desc: 'Achieved >= 80% weekly exercise adherence.',
      check: (state) => getWeeklyOverallPct(state) >= 80
    }
  ];

  // Default state for initial seed
  const DEFAULT_ASTRA_STATE = {
    activeDay: 1,
    activeCategory: 'all',
    streakDays: 14,
    // Pre-seed some completions for realistic mission feeling (Day 1: 3 of 5 done)
    completed: {
      'd1_t1': true,
      'd1_t2': true,
      'd1_t3': true,
      'd2_t1': true,
      'd2_t3': true,
      'd3_t1': true,
      'd3_t4': true,
      'd4_t1': true,
      'd4_t2': true,
      'd4_t3': true,
      'd5_t1': true,
      'd5_t2': true,
      'd6_t1': true,
      'd7_t1': true
    }
  };

  let astraState = null;
  let weeklyChartInstance = null;

  // --- Calculation Helpers ---

  function getDayData(dayNum) {
    return ASTRA_SCHEDULE_DATA.find(d => d.dayNum === dayNum) || ASTRA_SCHEDULE_DATA[0];
  }

  function getDayCompletionCount(state, dayNum) {
    const day = getDayData(dayNum);
    let done = 0;
    day.tasks.forEach(t => {
      if (state.completed && state.completed[t.id]) done++;
    });
    return { done, total: day.tasks.length };
  }

  function getDayCompletionPct(state, dayNum) {
    const { done, total } = getDayCompletionCount(state, dayNum);
    return total > 0 ? Math.round((done / total) * 100) : 0;
  }

  function getWeeklyOverallPct(state) {
    let totalDone = 0;
    let totalTasks = 0;
    ASTRA_SCHEDULE_DATA.forEach(d => {
      const counts = getDayCompletionCount(state, d.dayNum);
      totalDone += counts.done;
      totalTasks += counts.total;
    });
    return totalTasks > 0 ? Math.round((totalDone / totalTasks) * 100) : 0;
  }

  // --- Local Storage Management ---

  function loadAstraState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.activeDay === 'number' && parsed.completed) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('[ASTRA] Failed to load local storage, loading default seed.', e);
    }
    return JSON.parse(JSON.stringify(DEFAULT_ASTRA_STATE));
  }

  function saveAstraState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(astraState));
    } catch (e) {
      console.error('[ASTRA] Failed to save state to localStorage', e);
    }
  }

  // --- Rendering UI Modules ---

  function renderBannerDashboard() {
    const day = getDayData(astraState.activeDay);
    const { done, total } = getDayCompletionCount(astraState, astraState.activeDay);
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;

    const missionStatusEl = document.getElementById('astraMissionStatus');
    const missionTitleEl = document.getElementById('astraMissionTitle');
    const missionSubtitleEl = document.getElementById('astraMissionSubtitle');
    const completionPctEl = document.getElementById('astraCompletionPct');
    const taskRatioEl = document.getElementById('astraTaskRatio');
    const progressBarEl = document.getElementById('astraProgressBar');
    const motivationQuoteEl = document.getElementById('astraMotivationQuote');
    const streakCounterEl = document.getElementById('astraStreakCounter');

    if (missionStatusEl) {
      if (pct === 100) {
        missionStatusEl.className = 'badge badge-nominal mono-num';
        missionStatusEl.textContent = 'DAY COMPLETE';
      } else if (pct > 0) {
        missionStatusEl.className = 'badge badge-warn mono-num';
        missionStatusEl.textContent = 'IN PROGRESS';
      } else {
        missionStatusEl.className = 'badge badge-ghost mono-num';
        missionStatusEl.textContent = 'PENDING';
      }
    }

    if (missionTitleEl) missionTitleEl.textContent = day.title;
    if (missionSubtitleEl) missionSubtitleEl.textContent = day.subtitle;
    if (completionPctEl) completionPctEl.textContent = `${pct}%`;
    if (taskRatioEl) taskRatioEl.textContent = `${done} / ${total}`;
    if (progressBarEl) {
      progressBarEl.style.width = `${pct}%`;
      progressBarEl.parentElement.setAttribute('aria-valuenow', pct);
    }

    if (motivationQuoteEl) {
      motivationQuoteEl.innerHTML = `<span style="color:var(--accent-vermilion);">&#9656; NASA Protocol Note:</span> "${day.quote}"`;
    }

    if (streakCounterEl) {
      streakCounterEl.textContent = `🔥 ${astraState.streakDays || 14}-Day Consistency Streak`;
    }
  }

  function renderDaySelectorStrip() {
    const wrap = document.getElementById('astraDaySelectorStrip');
    if (!wrap) return;

    const html = ASTRA_SCHEDULE_DATA.map(day => {
      const { done, total } = getDayCompletionCount(astraState, day.dayNum);
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      const isActive = day.dayNum === astraState.activeDay;

      return `
        <div class="day-select-card ${isActive ? 'active' : ''}" data-day="${day.dayNum}">
          <span class="day-num">DAY 0${day.dayNum}</span>
          <div class="day-focus" title="${day.focus}">${day.focus}</div>
          <div class="day-status mono-num">${done}/${total} (${pct}%)</div>
        </div>
      `;
    }).join('');

    wrap.innerHTML = html;

    // Attach click listeners to cards
    wrap.querySelectorAll('.day-select-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const d = Number(e.currentTarget.getAttribute('data-day'));
        if (d && d !== astraState.activeDay) {
          astraState.activeDay = d;
          saveAstraState();
          updateAllViews();
        }
      });
    });
  }

  function renderExerciseCards() {
    const grid = document.getElementById('exerciseCardsGrid');
    const summaryEl = document.getElementById('activeDayFocusSummary');
    if (!grid) return;

    const day = getDayData(astraState.activeDay);
    if (summaryEl) {
      summaryEl.textContent = `Displaying ${day.title}`;
    }

    // Filter tasks if category filter is set
    let tasks = day.tasks;
    if (astraState.activeCategory && astraState.activeCategory !== 'all') {
      tasks = tasks.filter(t => t.category === astraState.activeCategory);
    }

    if (tasks.length === 0) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:30px;color:var(--ink-muted-paper);background:var(--bg-paper);border:1px dashed var(--border-paper);border-radius:6px;">
          No exercises found for category "<strong>${astraState.activeCategory}</strong>" on this day.
        </div>
      `;
      return;
    }

    const html = tasks.map(task => {
      const isDone = !!(astraState.completed && astraState.completed[task.id]);
      const equipBadgeClass = task.equipClass || 'other';

      return `
        <div class="exercise-task-card ${isDone ? 'completed' : ''}" data-task-id="${task.id}">
          <div class="exercise-card-head">
            <div class="exercise-checkbox-wrap">
              <input type="checkbox" class="exercise-checkbox" id="chk_${task.id}" data-task-id="${task.id}" ${isDone ? 'checked' : ''} aria-label="Mark ${task.name} complete">
              <div>
                <label for="chk_${task.id}" style="font-weight:700;font-size:14.5px;cursor:pointer;display:block;">${task.name}</label>
                <span class="mono-num" style="font-size:11px;color:var(--accent-vermilion-paper);">${task.category} &bull; ${task.subgroup}</span>
              </div>
            </div>
            <span class="exercise-equip-badge ${equipBadgeClass}">${task.equipment}</span>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;font-size:12px;background:var(--bg-paper);padding:6px 10px;border-radius:4px;border:1px solid var(--border-paper);">
            <span class="mono-num" style="color:var(--ink-muted-paper);">DURATION: <strong>${task.duration}</strong></span>
            <span class="mono-num" style="color:var(--accent-nominal-dark);font-weight:600;">${task.prescription}</span>
          </div>

          <div class="exercise-instructions">
            <strong>Clinical Protocol:</strong> ${task.instructions}
          </div>
        </div>
      `;
    }).join('');

    grid.innerHTML = html;

    // Attach checkbox event listeners
    grid.querySelectorAll('.exercise-checkbox').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const taskId = e.target.getAttribute('data-task-id');
        const checked = e.target.checked;

        if (!astraState.completed) astraState.completed = {};
        astraState.completed[taskId] = checked;
        saveAstraState();

        const card = e.target.closest('.exercise-task-card');
        if (card) {
          if (checked) card.classList.add('completed');
          else card.classList.remove('completed');
        }

        renderBannerDashboard();
        renderDaySelectorStrip();
        renderWeeklyAnalytics();
        renderGamificationBadges();
      });
    });
  }

  function renderWeeklyAnalytics() {
    // 1. Calculate summary metrics
    const overallPct = getWeeklyOverallPct(astraState);

    let totalMins = 0;
    const coveredGroups = new Set();

    ASTRA_SCHEDULE_DATA.forEach(d => {
      d.tasks.forEach(t => {
        if (astraState.completed && astraState.completed[t.id]) {
          totalMins += (t.durationMinutes || 20);
          coveredGroups.add(t.category);
        }
      });
    });

    const totalHours = (totalMins / 60).toFixed(1);

    const statWeeklyConsistency = document.getElementById('statWeeklyConsistency');
    const statTotalDuration = document.getElementById('statTotalDuration');
    const statGroupsCovered = document.getElementById('statGroupsCovered');

    if (statWeeklyConsistency) statWeeklyConsistency.textContent = `${overallPct}%`;
    if (statTotalDuration) statTotalDuration.textContent = `${totalHours} hrs`;
    if (statGroupsCovered) statGroupsCovered.textContent = `${coveredGroups.size} of 5`;

    // 2. Render Chart.js
    const canvas = document.getElementById('weeklyProgressChart');
    if (!canvas || typeof Chart === 'undefined') return;

    const labels = ASTRA_SCHEDULE_DATA.map(d => `Day ${d.dayNum}`);
    const pctData = ASTRA_SCHEDULE_DATA.map(d => getDayCompletionPct(astraState, d.dayNum));

    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const gridColor = isLight ? 'rgba(0, 0, 0, 0.06)' : 'rgba(255, 255, 255, 0.08)';
    const textColor = isLight ? '#4B5563' : '#8A99AD';

    if (weeklyChartInstance) {
      weeklyChartInstance.destroy();
    }

    weeklyChartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Completion (%)',
            data: pctData,
            backgroundColor: pctData.map(val => {
              if (val === 100) return isLight ? '#1C7C54' : '#28B074';
              if (val >= 60) return isLight ? '#2B6CA3' : '#00E5FF';
              return isLight ? '#D14D28' : '#FB8C00';
            }),
            borderRadius: 4,
            borderWidth: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `Completed: ${ctx.raw}%`
            }
          }
        },
        scales: {
          x: {
            grid: { color: gridColor },
            ticks: { color: textColor, font: { size: 10.5, family: 'Space Grotesk, sans-serif' } }
          },
          y: {
            min: 0,
            max: 100,
            grid: { color: gridColor },
            ticks: {
              stepSize: 25,
              color: textColor,
              font: { size: 10.5, family: 'Space Grotesk, monospace' },
              callback: (v) => `${v}%`
            }
          }
        }
      }
    });
  }

  function renderGamificationBadges() {
    const rack = document.getElementById('badgesRack');
    const countEl = document.getElementById('unlockedBadgesCount');
    if (!rack) return;

    let unlockedCount = 0;

    const html = MASTER_BADGES.map(b => {
      const isUnlocked = b.check(astraState);
      if (isUnlocked) unlockedCount++;

      return `
        <div class="badge-medal-item ${isUnlocked ? 'unlocked' : 'locked'}">
          <div class="badge-medal-icon">${b.icon}</div>
          <div class="badge-medal-title">${b.title}</div>
          <div class="badge-medal-desc">${b.desc}</div>
          <span class="badge ${isUnlocked ? 'badge-nominal' : 'badge-ghost'}" style="font-size:9.5px;padding:2px 6px;">
            ${isUnlocked ? 'UNLOCKED' : 'LOCKED'}
          </span>
        </div>
      `;
    }).join('');

    rack.innerHTML = html;

    if (countEl) {
      countEl.textContent = `${unlockedCount} / ${MASTER_BADGES.length} Unlocked`;
    }
  }

  function updateAllViews() {
    renderBannerDashboard();
    renderDaySelectorStrip();
    renderExerciseCards();
    renderWeeklyAnalytics();
    renderGamificationBadges();
  }

  // --- Wire User Actions ---

  function wireCategoryFilters() {
    const buttons = document.querySelectorAll('.cat-filter-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        buttons.forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        astraState.activeCategory = e.currentTarget.getAttribute('data-cat');
        saveAstraState();
        renderExerciseCards();
      });
    });
  }

  function wireActionButtons() {
    // Reset Today's Tasks
    const resetTodayBtn = document.getElementById('resetAstraTodayBtn');
    if (resetTodayBtn) {
      resetTodayBtn.addEventListener('click', () => {
        const day = getDayData(astraState.activeDay);
        if (confirm(`Reset all exercise checkboxes for ${day.title}? Other days will not be changed.`)) {
          day.tasks.forEach(t => {
            if (astraState.completed) {
              delete astraState.completed[t.id];
            }
          });
          saveAstraState();
          updateAllViews();
        }
      });
    }

    // Reset to NASA Seed
    const resetSeedBtn = document.getElementById('resetAstraSeedBtn');
    if (resetSeedBtn) {
      resetSeedBtn.addEventListener('click', () => {
        if (confirm('Reset ASTRA Muscle Missions back to NASA baseline flight schedule seed?')) {
          astraState = JSON.parse(JSON.stringify(DEFAULT_ASTRA_STATE));
          saveAstraState();
          updateAllViews();
        }
      });
    }
  }

  function initAll() {
    if (global.BioShell && typeof global.BioShell.renderShellChrome === 'function') {
      global.BioShell.renderShellChrome({ activeRoute: 'astra.html', showFooter: true });
    }
    astraState = loadAstraState();
    updateAllViews();
    wireCategoryFilters();
    wireActionButtons();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Export to global for debug or testing
  global.BioAstra = {
    getState: () => astraState,
    resetToSeed: () => {
      astraState = JSON.parse(JSON.stringify(DEFAULT_ASTRA_STATE));
      saveAstraState();
      initAll();
    }
  };

})(window);
