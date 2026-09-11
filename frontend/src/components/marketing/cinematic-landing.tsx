"use client";

import React, { useEffect, useRef } from "react";
import Link from "next/link";
import "./landing.css";

export function CinematicLanding() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // ==========================================================================
// HIRA — INTERACTIVE ORCHESTRATION & STORYTELLING CONTROLLER
// Real component choreography, animated SVG flow, WhatsApp simulation,
// subtle parallax, and scroll reveals
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  initHeroSimulation();
  initHeroParallax();
  initScrollStory();
  initFaqAccordion();

  // Calculate dynamic SVG wire coordinates after rendering
  requestAnimationFrame(updateWirePaths);
  window.addEventListener('resize', () => {
    requestAnimationFrame(updateWirePaths);
  });
});

/* --------------------------------------------------------------------------
   1. HERO PRODUCT ANIMATION CHOREOGRAPHY & MULTI-TURN DIALOGUE
-------------------------------------------------------------------------- */
const scenarios = {
  cleaning: {
    customerMsg: "Hi, do you have availability for a cleaning this Thursday?",
    customerTime: "9:41 AM",
    workTitle: "HIRA Autonomous Booking",
    steps: [
      { text: "Checking Google Calendar availability...", done: true },
      { text: "Verifying service area coverage & rates...", done: true },
      { text: "Syncing lead to CRM & alerting team dispatch...", done: true }
    ],
    hiraReplyMsg: "We have 10:00 AM and 2:30 PM open this Thursday. Which time works best for you?",
    hiraReplyTime: "9:41 AM",
    customerReplyMsg: "10:00 AM works perfectly!",
    customerReplyTime: "9:42 AM",
    confirmedBadge: "APPOINTMENT CONFIRMED",
    confirmedMsg: "You're all set! Cleaning booked for Thursday at 10:00 AM. Calendar invite & WhatsApp reminder sent.",
    confirmedTime: "9:42 AM",
    activeSystems: ["cal", "crm", "know", "team"]
  },
  dental: {
    customerMsg: "Can I book a consultation with Dr. Martinez tomorrow afternoon?",
    customerTime: "2:14 PM",
    workTitle: "HIRA Clinic Coordinator",
    steps: [
      { text: "Checking Dr. Martinez's clinic schedule...", done: true },
      { text: "Validating patient intake rules...", done: true },
      { text: "Reserving slot in Practice Management CRM...", done: true }
    ],
    hiraReplyMsg: "Dr. Martinez has an opening tomorrow at 3:30 PM. Would you like me to reserve this for you?",
    hiraReplyTime: "2:14 PM",
    customerReplyMsg: "Yes please, 3:30 PM is great.",
    customerReplyTime: "2:15 PM",
    confirmedBadge: "CONSULTATION CONFIRMED",
    confirmedMsg: "Confirmed! You're booked with Dr. Martinez for tomorrow at 3:30 PM. Pre-visit forms sent to this chat.",
    confirmedTime: "2:15 PM",
    activeSystems: ["cal", "crm", "know", "team"]
  },
  pricing: {
    customerMsg: "What are your business plans and does it include human escalation?",
    customerTime: "11:05 AM",
    workTitle: "HIRA Grounded Knowledge",
    steps: [
      { text: "Querying verified company FAQ documents...", done: true },
      { text: "Checking escalation SLA protocols...", done: true },
      { text: "Verifying zero-hallucination guardrails...", done: true }
    ],
    hiraReplyMsg: "Yes! All plans include human escalation, Google Calendar sync, and zero-hallucination guarantee. Would you like our Founder Beta tier?",
    hiraReplyTime: "11:05 AM",
    customerReplyMsg: "Can I get access to the Founder Beta?",
    customerReplyTime: "11:06 AM",
    confirmedBadge: "BETA INVITATION SENT",
    confirmedMsg: "Founder Beta access link and onboarding instructions sent to your WhatsApp!",
    confirmedTime: "11:06 AM",
    activeSystems: ["know", "crm"]
  },
  escalate: {
    customerMsg: "I need to discuss an urgent billing issue with your management team.",
    customerTime: "4:30 PM",
    workTitle: "HIRA Smart Escalation",
    steps: [
      { text: "Matching urgent escalation rule...", done: true },
      { text: "Pinging executive team on WhatsApp & dashboard...", done: true },
      { text: "Attaching full conversation audit trail...", done: true }
    ],
    hiraReplyMsg: "I've flagged this directly to Marcus on our executive team with your account details.",
    hiraReplyTime: "4:30 PM",
    customerReplyMsg: "Thank you, I'll wait for him.",
    customerReplyTime: "4:31 PM",
    confirmedBadge: "HUMAN HANDOFF ACTIVE",
    confirmedMsg: "Marcus is reviewing your account notes right now and will take over this thread in under 3 minutes.",
    confirmedTime: "4:31 PM",
    activeSystems: ["team", "crm"]
  }
};

let currentScenarioKey = 'cleaning';
let isSimulationPlaying = true;
let animTimeoutIds = [];

function clearAllTimers() {
  animTimeoutIds.forEach(id => clearTimeout(id));
  animTimeoutIds = [];
}

function queueTimer(fn, delay) {
  const id = setTimeout(fn, delay);
  animTimeoutIds.push(id);
  return id;
}

function initHeroSimulation() {
  const scenarioBtns = document.querySelectorAll('.sim-scenario-btn');
  const playBtn = document.getElementById('btn-play-sim');

  scenarioBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      scenarioBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentScenarioKey = btn.dataset.scenario;
      runSequence(currentScenarioKey);
    });
  });

  if (playBtn) {
    playBtn.addEventListener('click', () => {
      runSequence(currentScenarioKey);
    });
  }

  // Initial Run
  runSequence(currentScenarioKey);
}

function scrollChatToBottom() {
  const stream = document.getElementById('wa-conversation-stream');
  if (stream) {
    stream.scrollTo({
      top: stream.scrollHeight,
      behavior: 'smooth'
    });
  }
}

function runSequence(scenarioKey) {
  clearAllTimers();
  updateWirePaths();

  const data = scenarios[scenarioKey] || scenarios.cleaning;

  // Elements
  const bubbleCustomer = document.getElementById('wa-msg-customer');
  const bubbleCustomerText = document.getElementById('wa-customer-text');
  const bubbleCustomerTime = document.getElementById('wa-customer-time');

  const bubbleWork = document.getElementById('wa-msg-work');
  const workTitle = document.getElementById('wa-work-title');
  const checklistContainer = document.getElementById('wa-checklist-container');

  const bubbleHiraReply = document.getElementById('wa-msg-hira-reply');
  const bubbleHiraReplyText = document.getElementById('wa-hira-reply-text');
  const bubbleHiraReplyTime = document.getElementById('wa-hira-reply-time');

  const bubbleCustomerReply = document.getElementById('wa-msg-customer-reply');
  const bubbleCustomerReplyText = document.getElementById('wa-customer-reply-text');
  const bubbleCustomerReplyTime = document.getElementById('wa-customer-reply-time');

  const bubbleDone = document.getElementById('wa-msg-done');
  const bubbleDoneText = document.getElementById('wa-done-text');
  const bubbleDoneTime = document.getElementById('wa-done-time');

  const customerMsgNode = document.getElementById('node-customer-message');
  const hiraCenterNode = document.getElementById('node-hira-center');

  const wirePhoneToMsg = document.getElementById('wire-phone-to-msg');
  const wireMsgToHira = document.getElementById('wire-msg-to-hira');
  const wireHiraToCal = document.getElementById('wire-hira-to-cal');
  const wireHiraToCrm = document.getElementById('wire-hira-to-crm');
  const wireHiraToKnow = document.getElementById('wire-hira-to-know');
  const wireHiraToTeam = document.getElementById('wire-hira-to-team');

  const sysNodeCal = document.getElementById('sys-node-cal');
  const sysNodeCrm = document.getElementById('sys-node-crm');
  const sysNodeKnow = document.getElementById('sys-node-know');
  const sysNodeTeam = document.getElementById('sys-node-team');

  // Reset State
  bubbleCustomer.style.opacity = '0';
  bubbleCustomer.style.transform = 'translateY(12px)';

  if (bubbleWork) {
    bubbleWork.style.display = 'none';
    bubbleWork.style.opacity = '0';
  }
  if (bubbleHiraReply) {
    bubbleHiraReply.style.display = 'none';
    bubbleHiraReply.style.opacity = '0';
  }
  if (bubbleCustomerReply) {
    bubbleCustomerReply.style.display = 'none';
    bubbleCustomerReply.style.opacity = '0';
  }
  if (bubbleDone) {
    bubbleDone.style.display = 'none';
    bubbleDone.style.opacity = '0';
  }

  customerMsgNode.classList.remove('active');
  hiraCenterNode.classList.remove('processing');

  [wirePhoneToMsg, wireMsgToHira, wireHiraToCal, wireHiraToCrm, wireHiraToKnow, wireHiraToTeam].forEach(wire => {
    if (wire) wire.classList.remove('active');
  });

  [sysNodeCal, sysNodeCrm, sysNodeKnow, sysNodeTeam].forEach(node => {
    if (node) node.classList.remove('active');
  });

  const stream = document.getElementById('wa-conversation-stream');
  if (stream) stream.scrollTop = 0;

  // Step 1: Customer sends WhatsApp message (0.5s)
  queueTimer(() => {
    bubbleCustomerText.textContent = data.customerMsg;
    bubbleCustomerTime.textContent = data.customerTime;
    bubbleCustomer.style.opacity = '1';
    bubbleCustomer.style.transform = 'translateY(0)';
    scrollChatToBottom();

    // Pulse from phone to customer message node
    if (wirePhoneToMsg) wirePhoneToMsg.classList.add('active');
    customerMsgNode.classList.add('active');

    // Step 2: Connection travels toward HIRA (1.5s)
    queueTimer(() => {
      if (wireMsgToHira) wireMsgToHira.classList.add('active');

      // Step 3: HIRA activates (2.4s)
      queueTimer(() => {
        hiraCenterNode.classList.add('processing');

        if (workTitle) workTitle.textContent = data.workTitle || "HIRA Live Automation";
        bubbleWork.style.display = 'block';
        checklistContainer.innerHTML = '';
        data.steps.forEach(s => {
          const item = document.createElement('div');
          item.className = 'checklist-step loading';
          item.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="3"></circle></svg> <span>${s.text}</span>`;
          checklistContainer.appendChild(item);
        });

        setTimeout(() => {
          bubbleWork.style.opacity = '1';
          scrollChatToBottom();
        }, 50);

        // Step 4: Connections travel from HIRA to relevant systems (3.4s)
        queueTimer(() => {
          if (data.activeSystems.includes('cal')) {
            if (wireHiraToCal) wireHiraToCal.classList.add('active');
            if (sysNodeCal) sysNodeCal.classList.add('active');
          }
          if (data.activeSystems.includes('crm')) {
            if (wireHiraToCrm) wireHiraToCrm.classList.add('active');
            if (sysNodeCrm) sysNodeCrm.classList.add('active');
          }
          if (data.activeSystems.includes('know')) {
            if (wireHiraToKnow) wireHiraToKnow.classList.add('active');
            if (sysNodeKnow) sysNodeKnow.classList.add('active');
          }
          if (data.activeSystems.includes('team')) {
            if (wireHiraToTeam) wireHiraToTeam.classList.add('active');
            if (sysNodeTeam) sysNodeTeam.classList.add('active');
          }

          // Tick off steps in bubble
          const items = checklistContainer.querySelectorAll('.checklist-step');
          items.forEach((it, idx) => {
            setTimeout(() => {
              it.className = 'checklist-step done';
              it.innerHTML = `<svg width="12" height="12" fill="none" stroke="#25D366" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg> <span>${data.steps[idx].text}</span>`;
            }, idx * 450);
          });

          // Step 5: HIRA proposed reply appears in phone (5.0s)
          queueTimer(() => {
            if (bubbleHiraReply) {
              bubbleHiraReplyText.textContent = data.hiraReplyMsg;
              bubbleHiraReplyTime.textContent = data.hiraReplyTime;
              bubbleHiraReply.style.display = 'block';
              setTimeout(() => {
                bubbleHiraReply.style.opacity = '1';
                scrollChatToBottom();
              }, 50);
            }

            // Step 6: Customer confirms in phone (6.5s)
            queueTimer(() => {
              if (bubbleCustomerReply) {
                bubbleCustomerReplyText.textContent = data.customerReplyMsg;
                bubbleCustomerReplyTime.textContent = data.customerReplyTime;
                bubbleCustomerReply.style.display = 'block';
                setTimeout(() => {
                  bubbleCustomerReply.style.opacity = '1';
                  scrollChatToBottom();
                }, 50);
              }

              // Step 7: Final confirmation message appears in phone (7.8s)
              queueTimer(() => {
                if (bubbleDone) {
                  bubbleDoneText.textContent = data.confirmedMsg;
                  bubbleDoneTime.textContent = data.confirmedTime;
                  bubbleDone.style.display = 'block';
                  setTimeout(() => {
                    bubbleDone.style.opacity = '1';
                    scrollChatToBottom();
                  }, 50);
                }

                // Settle HIRA node back
                hiraCenterNode.classList.remove('processing');

                // Auto-loop after 9 seconds of idle
                queueTimer(() => {
                  if (isSimulationPlaying) {
                    runSequence(currentScenarioKey);
                  }
                }, 9000);

              }, 1300);

            }, 1500);

          }, 1600);

        }, 1000);

      }, 900);

    }, 1000);

  }, 500);
}

/* --------------------------------------------------------------------------
   2. DYNAMIC PIXEL-PERFECT SVG WIRE ALIGNMENT
-------------------------------------------------------------------------- */
function updateWirePaths() {
  const canvas = document.querySelector('.system-orchestration-canvas');
  const svg = document.querySelector('.svg-connection-layer');
  const phone = document.querySelector('.phone-mockup-container');
  const customerMsg = document.getElementById('node-customer-message');
  const hiraCenter = document.getElementById('node-hira-center');
  const calNode = document.getElementById('sys-node-cal');
  const crmNode = document.getElementById('sys-node-crm');
  const knowNode = document.getElementById('sys-node-know');
  const teamNode = document.getElementById('sys-node-team');

  if (!canvas || !svg || !phone || !customerMsg || !hiraCenter) return;

  const canvasRect = canvas.getBoundingClientRect();
  if (canvasRect.width === 0 || canvasRect.height === 0) return;

  svg.setAttribute('viewBox', `0 0 ${canvasRect.width} ${canvasRect.height}`);

  const getRel = (rect) => ({
    left: rect.left - canvasRect.left,
    right: rect.right - canvasRect.left,
    top: rect.top - canvasRect.top,
    bottom: rect.bottom - canvasRect.top,
    width: rect.width,
    height: rect.height,
    cx: rect.left - canvasRect.left + rect.width / 2,
    cy: rect.top - canvasRect.top + rect.height / 2
  });

  const p = getRel(phone.getBoundingClientRect());
  const mBox = customerMsg.querySelector('.node-msg-icon-box') || customerMsg;
  const m = getRel(mBox.getBoundingClientRect());
  const hBox = hiraCenter.querySelector('.node-hira-box') || hiraCenter;
  const h = getRel(hBox.getBoundingClientRect());

  // Wire 1: Phone to Customer Message
  const wirePhoneMsg = document.getElementById('wire-phone-to-msg');
  if (wirePhoneMsg) {
    const yPhone = p.top + p.height * 0.48;
    wirePhoneMsg.setAttribute('d', `M ${p.right},${yPhone} L ${m.left},${m.cy}`);
  }

  // Wire 2: Customer Message to Central HIRA
  const wireMsgHira = document.getElementById('wire-msg-to-hira');
  if (wireMsgHira) {
    wireMsgHira.setAttribute('d', `M ${m.right},${m.cy} L ${h.left},${h.cy}`);
  }

  // Wire 3-6: HIRA to 4 System Nodes
  const sysWires = [
    { el: calNode, wireId: 'wire-hira-to-cal' },
    { el: crmNode, wireId: 'wire-hira-to-crm' },
    { el: knowNode, wireId: 'wire-hira-to-know' },
    { el: teamNode, wireId: 'wire-hira-to-team' }
  ];

  sysWires.forEach(({ el, wireId }) => {
    const wire = document.getElementById(wireId);
    if (el && wire) {
      const icon = el.querySelector('.system-node-icon') || el;
      const s = getRel(icon.getBoundingClientRect());
      const cpx = h.right + (s.left - h.right) * 0.45;
      wire.setAttribute('d', `M ${h.right},${h.cy} C ${cpx},${h.cy} ${cpx},${s.cy} ${s.left},${s.cy}`);
    }
  });
}

/* --------------------------------------------------------------------------
   2. SUBTLE PARALLAX & 3D INTERACTION
-------------------------------------------------------------------------- */
function initHeroParallax() {
  const heroSection = document.querySelector('.cinematic-hero-section');
  const backdrop = document.querySelector('.hero-atmosphere-backdrop');
  const phone = document.querySelector('.phone-mockup-container');

  if (!heroSection || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  heroSection.addEventListener('mousemove', (e) => {
    const rect = heroSection.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    if (backdrop) {
      backdrop.style.transform = `scale(1.03) translate(${x * 14}px, ${y * 10}px)`;
    }
    if (phone) {
      phone.style.transform = `perspective(1200px) rotateY(${-7 + x * 8}deg) rotateX(${3 - y * 6}deg)`;
    }
  });

  heroSection.addEventListener('mouseleave', () => {
    if (backdrop) backdrop.style.transform = '';
    if (phone) phone.style.transform = '';
  });
}

/* --------------------------------------------------------------------------
   3. SCROLL-BASED STORYTELLING REVEALS
-------------------------------------------------------------------------- */
function initScrollStory() {
  const revealElements = document.querySelectorAll(
    '.problem-stat-card, .feat-bento-card, .step-card-item, .journey-node-step'
  );

  if (!('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  revealElements.forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
    observer.observe(el);
  });
}

/* --------------------------------------------------------------------------
   4. FAQ ACCORDION
-------------------------------------------------------------------------- */
function initFaqAccordion() {
  const entries = document.querySelectorAll('.faq-entry');
  entries.forEach(entry => {
    const btn = entry.querySelector('.faq-btn');
    btn.addEventListener('click', () => {
      const isOpen = entry.classList.contains('open');
      entries.forEach(e => e.classList.remove('open'));
      if (!isOpen) {
        entry.classList.add('open');
      }
    });
  });
}


  }, []);

  return (
    <div ref={containerRef} className="cinematic-landing-root">
      {/*  ==========================================================================
       MAIN NAVIGATION
       ==========================================================================  */}
  <nav className="site-nav">
    <div className="nav-container">
      <a href="#" className="brand-wrap" title="HIRA by Stoneveil">
        <img src="/assets/stoneveil-emblem-transparent.png" alt="Stoneveil" className="brand-stoneveil-logo" />
        <div className="brand-text-block">
          <span className="brand-name">HIRA</span>
          <span className="brand-company-tag">BY STONEVEIL</span>
        </div>
      </a>

      <ul className="nav-menu">
        <li><a href="#features">Features</a></li>
        <li><a href="#how-it-works">How it works</a></li>
        <li><a href="#journey">Journey</a></li>
        <li><a href="#faq">FAQ</a></li>
      </ul>

      <div className="nav-actions">
        <a href="/sign-in" className="nav-link-btn">Sign in</a>
        <a href="/sign-up" className="btn-pill-white">Get started</a>
      </div>
    </div>
  </nav>

  {/*  ==========================================================================
       CINEMATIC HERO EXPERIENCE
       ==========================================================================  */}
  <header className="cinematic-hero-section">
    {/*  Atmospheric AI Layer  */}
    <div className="hero-atmosphere-backdrop"></div>
    <div className="hero-scrim-left"></div>
    <div className="hero-scrim-bottom"></div>

    <div className="hero-inner-container">
      {/*  Left Column: Copy & Value Proposition  */}
      <div className="hero-copy-col">
        <div className="founder-beta-tag">
          <span className="pulse-dot"></span>
          <span>FOUNDER BETA — LIMITED EARLY ACCESS</span>
        </div>

        <h1 className="hero-headline">
          Never miss<br />
          another<br />
          <span className="coral-accent">customer</span> message.
        </h1>

        <p className="hero-subheadline">
          HIRA answers your customers on WhatsApp, books appointments, follows up on leads, and hands the conversation to your team the moment it needs a human touch.
        </p>

        <div className="hero-cta-wrapper">
          <a href="#get-started" className="hero-cta-btn">
            <span>Get started</span>
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
          </a>
        </div>

        {/*  Trust Badges Strip (Exact from reference)  */}
        <div className="hero-trust-strip">
          <span className="trust-title">TRUSTED BY MODERN BUSINESSES</span>
          <div className="trust-pills-row">
            <span className="trust-pill">
              <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><path d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6z"/></svg>
              Clinics
            </span>
            <span className="trust-pill">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.242 4.243 3 3 0 004.242-4.243zm0-5.758a3 3 0 10-4.242-4.243 3 3 0 004.242 4.243z"></path></svg>
              Salons
            </span>
            <span className="trust-pill">
              <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24"><path d="M20.57 14.86L22 13.43 20.57 12 17 15.57 8.43 7 12 3.43 10.57 2 9.14 3.43 7.71 2 5.57 4.14 4.14 2.71 2.71 4.14l1.43 1.43L2 7.71l1.43 1.43L2 10.57 3.43 12 7 8.43 15.57 17 12 20.57 13.43 22l1.43-1.43L16.29 22l2.14-2.14 1.43 1.43 1.43-1.43-1.43-1.43L22 16.29z"/></svg>
              Fitness
            </span>
            <span className="trust-pill">
              <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
              Real Estate
            </span>
            <span className="trust-pill">⋯ And more</span>
          </div>
        </div>

        {/*  Simulation Interactive Scenario Selector  */}
        <div className="sim-playback-controls">
          <span style={{fontSize: '0.6875rem', color: 'var(--text-muted)', fontWeight: '700', textTransform: 'uppercase'}}>Demo:</span>
          <button className="sim-btn sim-scenario-btn active" data-scenario="cleaning">Booking</button>
          <button className="sim-btn sim-scenario-btn" data-scenario="dental">Clinic</button>
          <button className="sim-btn sim-scenario-btn" data-scenario="pricing">Knowledge</button>
          <button className="sim-btn sim-scenario-btn" data-scenario="escalate">Escalation</button>
          <button className="sim-btn" id="btn-play-sim" title="Replay Flow">
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            Replay
          </button>
        </div>
      </div>

      {/*  Right Column: Real Animated Product Demonstration (Exact from media_469)  */}
      <div className="hero-product-stage">
        <div className="system-orchestration-canvas">

          {/*  SVG Dynamic Connection Lines  */}
          <svg className="svg-connection-layer" viewBox="0 0 920 540" preserveAspectRatio="none">
            {/*  Wire: Phone to Customer Message Node  */}
            <path id="wire-phone-to-msg" className="flow-wire" d="M 285,260 L 375,260" />

            {/*  Wire: Customer Message Node to Central HIRA  */}
            <path id="wire-msg-to-hira" className="flow-wire" d="M 435,260 L 485,260" />

            {/*  Wire: HIRA to Calendar  */}
            <path id="wire-hira-to-cal" className="flow-wire" d="M 555,260 C 600,260 610,105 670,105" />

            {/*  Wire: HIRA to CRM  */}
            <path id="wire-hira-to-crm" className="flow-wire" d="M 555,260 C 600,260 610,210 670,210" />

            {/*  Wire: HIRA to Knowledge  */}
            <path id="wire-hira-to-know" className="flow-wire" d="M 555,260 C 600,260 610,315 670,315" />

            {/*  Wire: HIRA to Team  */}
            <path id="wire-hira-to-team" className="flow-wire" d="M 555,260 C 600,260 610,420 670,420" />
          </svg>

          {/*  1. REAL 3D ANGLED SMARTPHONE  */}
          <div className="phone-mockup-container">
            <div className="phone-outer-chassis">
              <div className="phone-screen-glare"></div>
              
              <div className="phone-screen-inner">
                {/*  Status Bar  */}
                <div className="phone-status-bar">
                  <span>9:41</span>
                  <div className="dynamic-island"></div>
                  <div className="status-icons-right">
                    {/*  Signal, Wifi, Battery SVGs  */}
                    <svg width="14" height="10" viewBox="0 0 16 12" fill="currentColor"><path d="M1 9h2v3H1zm4-3h2v6H5zm4-3h2v9H9zm4-3h2v12h-2z"/></svg>
                    <svg width="12" height="10" viewBox="0 0 16 12" fill="currentColor"><path d="M8 3a8.9 8.9 0 00-6.3 2.6L8 12l6.3-6.4A8.9 8.9 0 008 3z"/></svg>
                    <svg width="16" height="10" viewBox="0 0 24 12" fill="currentColor"><rect x="1" y="1" width="18" height="10" rx="3" fill="none" stroke="currentColor" strokeWidth="2"/><rect x="3" y="3" width="12" height="6" rx="1.5"/><path d="M21 4.5v3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                  </div>
                </div>

                {/*  WhatsApp In-App Header  */}
                <div className="wa-app-header">
                  <div className="wa-header-left">
                    <span className="wa-back-arrow">
                      <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7"></path></svg>
                    </span>
                    <div className="wa-avatar">
                      <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0012.04 2z"/></svg>
                      <span className="wa-online-dot"></span>
                    </div>
                    <div className="wa-user-details">
                      <div className="wa-name">Customer</div>
                      <div className="wa-status">online</div>
                    </div>
                  </div>
                  <div className="wa-header-icons">
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M17 10.5V7a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h12a1 1 0 001-1v-3.5l4 4v-11l-4 4z"/></svg>
                    <svg width="15" height="15" fill="currentColor" viewBox="0 0 24 24"><path d="M20.01 15.38c-1.23 0-2.42-.2-3.53-.56a.977.977 0 00-1.01.24l-2.2 2.2a15.053 15.053 0 01-6.59-6.59l2.2-2.21a.96.96 0 00.25-1A11.36 11.36 0 018.5 3.93c0-.53-.44-.93-.96-.93H4c-.53 0-1 .44-1 .96 0 9.42 7.64 17.06 17.06 17.06.53 0 .95-.44.95-.96v-3.56c0-.52-.42-.96-.95-.96z"/></svg>
                  </div>
                </div>

                {/*  Chat Conversation Stream  */}
                <div className="wa-conversation-body" id="wa-conversation-stream">
                  {/*  Message 1: Customer Inbound  */}
                  <div className="wa-bubble-customer" id="wa-msg-customer">
                    <div id="wa-customer-text">Hi, do you have availability for a cleaning this Thursday?</div>
                    <div className="bubble-time">
                      <span id="wa-customer-time">9:41 AM</span>
                      <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7m-4-6l-4 4"></path></svg>
                    </div>
                  </div>

                  {/*  Message 2: HIRA Processing / Checklist  */}
                  <div className="wa-bubble-hira-work" id="wa-msg-work" style={{display: 'none'}}>
                    <div className="hira-brand-mini-badge">
                      <img src="/assets/stoneveil-emblem-transparent.png" alt="Stoneveil" className="wa-mini-logo" />
                      <span id="wa-work-title">HIRA Live Automation</span>
                    </div>
                    <div className="hira-checklist-items" id="wa-checklist-container">
                      {/*  Dynamic steps injected here  */}
                    </div>
                  </div>

                  {/*  Message 3: HIRA Proposed Reply  */}
                  <div className="wa-bubble-hira-reply" id="wa-msg-hira-reply" style={{display: 'none'}}>
                    <div id="wa-hira-reply-text">We have 10:00 AM and 2:30 PM open this Thursday. Which time works best for you?</div>
                    <div className="bubble-time">
                      <span id="wa-hira-reply-time">9:41 AM</span>
                    </div>
                  </div>

                  {/*  Message 4: Customer Reply  */}
                  <div className="wa-bubble-customer" id="wa-msg-customer-reply" style={{display: 'none'}}>
                    <div id="wa-customer-reply-text">10:00 AM works perfectly!</div>
                    <div className="bubble-time">
                      <span id="wa-customer-reply-time">9:42 AM</span>
                      <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7m-4-6l-4 4"></path></svg>
                    </div>
                  </div>

                  {/*  Message 5: HIRA Final Confirmation Badge  */}
                  <div className="wa-bubble-hira-done" id="wa-msg-done" style={{display: 'none'}}>
                    <div className="done-badge-header">
                      <svg width="14" height="14" fill="none" stroke="#25D366" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7"></path></svg>
                      <span>APPOINTMENT CONFIRMED</span>
                    </div>
                    <div id="wa-done-text">You're all set! Cleaning booked for Thursday at 10:00 AM. Calendar invite and WhatsApp reminder sent.</div>
                    <div className="bubble-time" style={{display: 'flex', justifyContent: 'flex-end', gap: '4px', fontSize: '0.65rem', color: 'rgba(255,255,255,0.6)', marginTop: '6px'}}>
                      <span id="wa-done-time">9:42 AM</span>
                      <svg width="12" height="12" fill="none" stroke="#25D366" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7m-4-6l-4 4"></path></svg>
                    </div>
                  </div>
                </div>

                {/*  Bottom Input Bar  */}
                <div className="wa-input-bar">
                  <span style={{color: 'var(--text-muted)', fontSize: '1.1rem'}}>+</span>
                  <div className="wa-input-box">Message</div>
                  <svg width="16" height="16" fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path></svg>
                  <svg width="16" height="16" fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
                </div>
              </div>
            </div>
          </div>

          {/*  2. ORCHESTRATION PIPELINE NODES  */}
          <div className="flow-nodes-wrapper">
            {/*  Node: Customer Message  */}
            <div className="node-customer-msg" id="node-customer-message">
              <div className="node-msg-icon-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                  <path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0012.04 2z" fill="#FFFFFF" fillOpacity="0.15" stroke="#FFFFFF" strokeWidth="1.8"/>
                  <path d="M8.5 12h7M8.5 9h4M8.5 15h5" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </div>
              <span className="node-msg-label">Customer message</span>
            </div>

            {/*  Node: Central HIRA Node  */}
            <div className="node-hira-center" id="node-hira-center">
              <div className="node-hira-box">
                <img src="/assets/stoneveil-emblem-large-transparent.png" alt="Stoneveil Core" className="node-stoneveil-emblem" />
              </div>
              <span className="node-hira-label">HIRA CORE</span>
            </div>

            {/*  Node 3: 4 Branching System Nodes  */}
            <div className="branch-systems-col">
              {/*  Calendar  */}
              <div className="system-node-item" id="sys-node-cal">
                <div className="system-node-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="sys-svg">
                    <rect x="3" y="4" width="18" height="17" rx="3" fill="#FFFFFF" fillOpacity="0.12" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <line x1="3" y1="9" x2="21" y2="9" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <line x1="8" y1="2" x2="8" y2="5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round"/>
                    <line x1="16" y1="2" x2="16" y2="5" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round"/>
                    <circle cx="7.5" cy="13" r="1.2" fill="#FFFFFF"/>
                    <circle cx="12" cy="13" r="1.2" fill="#FFFFFF"/>
                    <circle cx="16.5" cy="13" r="1.2" fill="#FFFFFF"/>
                    <circle cx="7.5" cy="17" r="1.2" fill="#FFFFFF"/>
                    <circle cx="12" cy="17" r="1.2" fill="#FFFFFF"/>
                    <circle cx="16.5" cy="17" r="1.5" fill="#FFFFFF"/>
                  </svg>
                </div>
                <div className="system-node-text">
                  <div className="sys-title">Calendar</div>
                  <div className="sys-desc">Checks availability</div>
                </div>
              </div>

              {/*  CRM  */}
              <div className="system-node-item" id="sys-node-crm">
                <div className="system-node-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="sys-svg">
                    <rect x="3" y="3" width="18" height="18" rx="3" fill="#FFFFFF" fillOpacity="0.12" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <circle cx="12" cy="9" r="3" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <path d="M7 17c0-2.2 2.2-3.8 5-3.8s5 1.6 5 3.8" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round"/>
                    <circle cx="18" cy="6" r="2.2" fill="#FFFFFF" stroke="#000000" strokeWidth="1.4"/>
                  </svg>
                </div>
                <div className="system-node-text">
                  <div className="sys-title">CRM</div>
                  <div className="sys-desc">Updates leads</div>
                </div>
              </div>

              {/*  Knowledge  */}
              <div className="system-node-item" id="sys-node-know">
                <div className="system-node-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="sys-svg">
                    <path d="M16 2H8C6.9 2 6 2.9 6 4v11" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" strokeOpacity="0.5"/>
                    <path d="M9 5h7.6a2 2 0 011.4.6l2.4 2.4a2 2 0 01.6 1.4V20a2 2 0 01-2 2H9a2 2 0 01-2-2V7a2 2 0 012-2z" fill="#FFFFFF" fillOpacity="0.12" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <path d="M16 5v4h4" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    <line x1="11" y1="13" x2="17" y2="13" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round"/>
                    <line x1="11" y1="17" x2="15" y2="17" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round"/>
                    <circle cx="17.5" cy="17" r="1.5" fill="#FFFFFF"/>
                  </svg>
                </div>
                <div className="system-node-text">
                  <div className="sys-title">Knowledge</div>
                  <div className="sys-desc">Finds the right info</div>
                </div>
              </div>

              {/*  Team  */}
              <div className="system-node-item" id="sys-node-team">
                <div className="system-node-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="sys-svg">
                    <rect x="3" y="11" width="2.5" height="5.5" rx="1.2" fill="#FFFFFF"/>
                    <rect x="18.5" y="11" width="2.5" height="5.5" rx="1.2" fill="#FFFFFF"/>
                    <path d="M4.25 13V9a7.75 7.75 0 0115.5 0v4" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <circle cx="12" cy="11" r="3" fill="#FFFFFF" fillOpacity="0.12" stroke="#FFFFFF" strokeWidth="1.8"/>
                    <path d="M7.5 19c.8-1.8 2.5-3 4.5-3s3.7 1.2 4.5 3" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round"/>
                    <path d="M19.5 15v1.5a2.5 2.5 0 01-2.5 2.5H15" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round"/>
                  </svg>
                </div>
                <div className="system-node-text">
                  <div className="sys-title">Team</div>
                  <div className="sys-desc">Escalates when needed</div>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/*  Ambient Watermark (from reference media_469)  */}
        <div className="hero-ambient-watermark">
          <span>AUTOMATE</span>
          <span>CONNECT</span>
          <span>GROW</span>
          <span>—</span>
        </div>
      </div>
    </div>
  </header>

  {/*  ==========================================================================
       SECTION 2: JOURNEY / FLOW ("From a message to meaningful action")
       ==========================================================================  */}
  <section className="section-journey-flow" id="journey">
    <div className="journey-bg-layer"></div>

    <div className="journey-inner-wrap">
      <div className="journey-header">
        <span className="journey-eyebrow">PHONE / FLOW ARCHITECTURE</span>
        <h2 className="journey-headline">From a message to meaningful action.</h2>
      </div>

      <div className="journey-path-track">
        {/*  Milestone 1  */}
        <div className="journey-node-step">
          <div className="journey-step-header">
            <div className="journey-icon-wrap">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#25D366" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"></path></svg>
            </div>
            <span className="journey-step-tag">01 · MESSAGE</span>
          </div>
          <h3>WhatsApp Arrives</h3>
          <p>The customer texts your existing WhatsApp Business number naturally. No apps to install or portals to log into.</p>
        </div>

        {/*  Milestone 2  */}
        <div className="journey-node-step">
          <div className="journey-step-header">
            <div className="journey-icon-wrap">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"></path></svg>
            </div>
            <span className="journey-step-tag">02 · UNDERSTAND</span>
          </div>
          <h3>Intent Parsing</h3>
          <p>HIRA extracts time preferences, service requests, and buyer context with zero latency or awkward syntax triggers.</p>
        </div>

        {/*  Milestone 3  */}
        <div className="journey-node-step">
          <div className="journey-step-header">
            <div className="journey-icon-wrap">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            </div>
            <span className="journey-step-tag">03 · CONNECT</span>
          </div>
          <h3>Subsystems Check</h3>
          <p>Queries your Google Calendar, searches verified company documents, and checks customer history in your CRM.</p>
        </div>

        {/*  Milestone 4  */}
        <div className="journey-node-step">
          <div className="journey-step-header">
            <div className="journey-icon-wrap">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FBBF24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
            </div>
            <span className="journey-step-tag">04 · AUTOMATE</span>
          </div>
          <h3>Autonomous Action</h3>
          <p>Locks in calendar appointments, updates deal stages, and crafts verified, natural WhatsApp responses instantly.</p>
        </div>

        {/*  Milestone 5  */}
        <div className="journey-node-step">
          <div className="journey-step-header">
            <div className="journey-icon-wrap">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>
            </div>
            <span className="journey-step-tag">05 · GROW</span>
          </div>
          <h3>Continuous Revenue</h3>
          <p>Captures every lead 24/7, follows up on stale chats, and delivers 840ms response times while your competitors sleep.</p>
        </div>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       SECTION 3: PROBLEM ("The Cost of Response Lag")
       ==========================================================================  */}
  <section className="section-problem-grid" id="problem">
    <div className="section-title-center">
      <span className="journey-eyebrow">The Cost of Response Lag</span>
      <h2 className="journey-headline" style={{fontSize: 'clamp(2.25rem, 4vw, 3rem)'}}>Customers message when you're busy.<br />Competitors reply when you're not.</h2>
    </div>

    <div className="problem-stat-cards">
      <div className="problem-stat-card">
        <div>
          <div className="problem-stat-icon-wrap">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"></path></svg>
          </div>
          <div className="problem-big-stat">68%</div>
          <h3>Inquiries outside business hours</h3>
          <p>Over two-thirds of customer WhatsApp messages arrive in the evenings and on weekends. Without automated AI handling, high-intent buyers bounce to another business.</p>
        </div>
      </div>

      <div className="problem-stat-card">
        <div>
          <div className="problem-stat-icon-wrap">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line><path d="M10 14h4l-2 3"></path></svg>
          </div>
          <div className="problem-big-stat">6 to 8</div>
          <h3>Messages to book one appointment</h3>
          <p>Constant back-and-forth scheduling friction drains your team's energy and loses customers in the delay. HIRA checks real availability and confirms in one turn.</p>
        </div>
      </div>

      <div className="problem-stat-card">
        <div>
          <div className="problem-stat-icon-wrap">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"></path><line x1="9" y1="10" x2="15" y2="10"></line></svg>
          </div>
          <div className="problem-big-stat">40%</div>
          <h3>Leads lost in scattered chats</h3>
          <p>Without unified CRM syncing, promising leads get buried in individual team members' WhatsApp chats and forgotten spreadsheets without follow-ups.</p>
        </div>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       SECTION 4: FEATURES ("One agent. Everything connected.")
       ==========================================================================  */}
  <section className="section-features-connected" id="features">
    <div className="features-inner-container">
      <div className="section-title-center">
        <span className="journey-eyebrow">CAPABILITIES</span>
        <h2 className="journey-headline">One agent. Everything connected.</h2>
        <p style={{color: 'var(--text-secondary)', marginTop: '12px', fontSize: '1.1rem'}}>Grounded intelligence engineered for real business operations.</p>
      </div>

      <div className="features-bento-grid">
        {/*  1. Knowledge Base  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
          </div>
          <h3>Knowledge base</h3>
          <p>Every answer comes from what you've actually told HIRA — imported from your website or written as FAQs — never a generic guess.</p>
        </div>

        {/*  2. Appointment Booking  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          </div>
          <h3>Appointment booking</h3>
          <p>No back-and-forth to find a time that works. HIRA Calendar checks real availability and books, reschedules, or cancels — no setup required, with optional Google Calendar sync.</p>
        </div>

        {/*  3. Assisted or Autonomous  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          </div>
          <h3>Assisted or Autonomous</h3>
          <p>You stay in control for as long as you want — review every reply and booking, or switch to fully autonomous once you trust it.</p>
        </div>

        {/*  4. Escalation to a Human  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
          </div>
          <h3>Escalation to a human</h3>
          <p>Customers never get stuck with a guess. Uncertain or sensitive conversations are flagged and handed to a person on your team.</p>
        </div>

        {/*  5. Lead Pipeline  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" strokeWidth="2"></circle><circle cx="12" cy="12" r="5" strokeWidth="2"></circle><circle cx="12" cy="12" r="1" strokeWidth="2"></circle></svg>
          </div>
          <h3>Lead pipeline</h3>
          <p>No lead falls through the cracks. Every conversation that looks like one is tracked automatically — new, contacted, qualified, won.</p>
        </div>

        {/*  6. Unified Inbox  */}
        <div className="feat-bento-card">
          <div className="feat-icon-box">
            <svg width="22" height="22" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>
          </div>
          <h3>Unified inbox</h3>
          <p>One place for the whole customer relationship — every conversation, appointment, and lead, with nothing lost in a separate spreadsheet.</p>
        </div>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       SECTION 5: HOW IT WORKS ("A simpler way to serve your customers")
       ==========================================================================  */}
  <section className="section-how-it-works" id="how-it-works">
    <div className="section-title-center">
      <span className="journey-eyebrow">HOW IT WORKS</span>
      <h2 className="journey-headline">Set up in four steps</h2>
      <p style={{color: 'var(--text-secondary)', marginTop: '12px'}}>A simpler way to serve your customers 24 hours a day.</p>
    </div>

    <div className="steps-progression-grid">
      <div className="step-card-item">
        <div className="step-number-disc">1</div>
        <h3>Teach it your business</h3>
        <p>Import your website or write FAQs so HIRA can answer from information you actually provided.</p>
      </div>

      <div className="step-card-item">
        <div className="step-number-disc">2</div>
        <h3>Connect WhatsApp</h3>
        <p>Link the WhatsApp Business number your customers already message.</p>
      </div>

      <div className="step-card-item">
        <div className="step-number-disc">3</div>
        <h3>Test it yourself</h3>
        <p>Try real conversations in Demo Chat before a single customer sees a reply.</p>
      </div>

      <div className="step-card-item">
        <div className="step-number-disc">4</div>
        <h3>Go live, at your pace</h3>
        <p>Start in Assisted Mode reviewing every reply, then switch a business to Autonomous once you trust it.</p>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       SECTION 6: FAQ ACCORDION (Verbatim Authentic Content)
       ==========================================================================  */}
  <section className="section-faq-accordion" id="faq">
    <div className="section-title-center">
      <span className="journey-eyebrow">FREQUENTLY ASKED QUESTIONS</span>
      <h2 className="journey-headline">Everything you need to know.</h2>
    </div>

    <div className="faq-list-wrap">
      {/*  Q1  */}
      <div className="faq-entry open">
        <button className="faq-btn">
          <span>Is HIRA a chatbot?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            No. A chatbot answers messages and stops there. HIRA is an AI employee — it holds the whole job: the conversation, your calendar, and your leads, together, grounded in what you've told it about your business.
          </div>
        </div>
      </div>

      {/*  Q2  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>Does HIRA reply to my customers automatically?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            It depends on the mode you choose. In Assisted Mode — the default — HIRA drafts every reply and proposed booking, and you approve, edit, or reject it before anything is sent. In Autonomous Mode, HIRA sends replies and makes bookings on its own. Most businesses start in Assisted Mode and move to Autonomous once they trust the AI's replies.
          </div>
        </div>
      </div>

      {/*  Q3  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>What happens if HIRA doesn't know the answer?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            It escalates the conversation to a human instead of guessing. Escalated conversations are flagged clearly in your dashboard so nothing gets missed.
          </div>
        </div>
      </div>

      {/*  Q4  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>Can it actually book appointments?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            Yes — HIRA Calendar checks real availability and can book, reschedule, or cancel appointments as part of the conversation, right out of the box. You can optionally connect Google Calendar later if you want everything synced there.
          </div>
        </div>
      </div>

      {/*  Q5  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>Do I need a WhatsApp Business account already?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            Yes. HIRA connects to a WhatsApp Business number you already have — it doesn't create one for you.
          </div>
        </div>
      </div>

      {/*  Q6  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>Is my business's data separated from other businesses using HIRA?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            Yes. Every business's conversations, customers, and knowledge base are isolated from every other business on the platform.
          </div>
        </div>
      </div>

      {/*  Q7  */}
      <div className="faq-entry">
        <button className="faq-btn">
          <span>What does HIRA cost?</span>
          <span className="faq-toggle-icon">+</span>
        </button>
        <div className="faq-pane">
          <div className="faq-pane-text">
            Pricing isn't public yet. Sign up to get started, or reach out once you're in the dashboard.
          </div>
        </div>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       SECTION 7: CLOSING CTA ("More conversations. A bigger tomorrow.")
       ==========================================================================  */}
  <section className="section-cinematic-cta" id="get-started">
    <div className="cta-celestial-box">
      <div className="cta-horizon-backdrop"></div>
      
      <div className="cta-content-relative">
        <span className="journey-eyebrow" style={{color: 'var(--accent-orange)', marginBottom: '16px'}}>MORE CONVERSATIONS. A BIGGER TOMORROW.</span>
        <h2 className="cta-heading">Never miss another message again</h2>
        <p className="cta-text">
          Set up your knowledge base, connect WhatsApp, and test HIRA yourself — before a single customer sees a reply.
        </p>
        <a href="#" className="btn-pill-white" style={{fontSize: '1.05rem', padding: '14px 36px'}}>
          <span>Get started</span>
          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
        </a>
      </div>
    </div>
  </section>

  {/*  ==========================================================================
       FOOTER
       ==========================================================================  */}
  <footer className="site-footer">
    <div className="footer-brand-col">
      <div className="footer-brand-lockup">
        <img src="/assets/stoneveil-lockup-transparent.png" alt="Stoneveil — Engineering the future of work" className="footer-logo-img" />
      </div>
      <p className="footer-tagline">ENGINEERING THE FUTURE OF WORK</p>
      <div className="footer-copy-text">
        © 2026 Stoneveil Technologies. All rights reserved.<br />
        <span className="footer-product-sub">HIRA is an autonomous AI employee engineered by Stoneveil.</span>
      </div>
    </div>

    <ul className="footer-nav">
      <li><a href="#">Sign in</a></li>
      <li><a href="#get-started">Get started</a></li>
      <li><a href="#">Privacy</a></li>
      <li><a href="#">Terms</a></li>
      <li><a href="#">Data Deletion</a></li>
      <li><a href="#">Contact</a></li>
      <li><a href="#">Company</a></li>
    </ul>
  </footer>
    </div>
  );
}
