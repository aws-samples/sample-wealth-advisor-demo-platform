export interface Meeting {
  id: string;
  clientName: string;
  time: string;
  type: string;
  date: string; // ISO date "YYYY-MM-DD"
}

export interface Alert {
  id: string;
  type: 'compliance' | 'market';
  title: string;
  message: string;
  severity: 'high' | 'medium' | 'low';
}

export interface Message {
  id: string;
  from: 'advisor' | 'client';
  text: string;
  timestamp: string;
}

export interface MessageThread {
  id: string;
  clientName: string;
  clientEmail: string;
  messages: Message[];
}

function getRelativeDate(daysFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().split('T')[0];
}

export const UPCOMING_MEETINGS: Meeting[] = [
  {
    id: '1',
    clientName: 'Michael Chen',
    time: '10:00 AM',
    type: 'Portfolio Review',
    date: getRelativeDate(0),
  },
  {
    id: '2',
    clientName: 'Sarah Johnson',
    time: '2:00 PM',
    type: 'Financial Planning',
    date: getRelativeDate(0),
  },
  {
    id: '3',
    clientName: 'David Lee',
    time: '4:00 PM',
    type: 'Investment Strategy',
    date: getRelativeDate(0),
  },
  {
    id: '4',
    clientName: 'Emma Wilson',
    time: '9:30 AM',
    type: 'Quarterly Review',
    date: getRelativeDate(1),
  },
  {
    id: '5',
    clientName: 'Robert Park',
    time: '11:00 AM',
    type: 'Tax Planning',
    date: getRelativeDate(1),
  },
  {
    id: '6',
    clientName: 'Lisa Wang',
    time: '3:00 PM',
    type: 'Estate Planning',
    date: getRelativeDate(2),
  },
  {
    id: '7',
    clientName: 'Michael Chen',
    time: '10:00 AM',
    type: 'Follow-up Review',
    date: getRelativeDate(3),
  },
  {
    id: '8',
    clientName: 'James Morrison',
    time: '1:00 PM',
    type: 'New Client Onboarding',
    date: getRelativeDate(4),
  },
  {
    id: '9',
    clientName: 'Sarah Johnson',
    time: '9:00 AM',
    type: 'Risk Assessment',
    date: getRelativeDate(5),
  },
  {
    id: '10',
    clientName: 'David Lee',
    time: '2:30 PM',
    type: 'Retirement Planning',
    date: getRelativeDate(7),
  },
];

export const ADVISOR_ALERTS: Alert[] = [
  {
    id: '1',
    type: 'compliance',
    title: 'Compliance Alert',
    message: 'Annual compliance review due for 5 clients',
    severity: 'high',
  },
  {
    id: '2',
    type: 'market',
    title: 'Market Alert',
    message: 'S&P 500 volatility increased by 15%',
    severity: 'medium',
  },
];

export const MESSAGE_THREADS: MessageThread[] = [
  {
    id: 'thread-1',
    clientName: 'Michael Chen',
    clientEmail: 'michael.chen@email.com',
    messages: [
      {
        id: 'm1',
        from: 'client',
        text: 'Hi, I wanted to discuss the recent portfolio rebalancing. The tech allocation seems higher than what we agreed on.',
        timestamp: '2026-07-28T09:15:00Z',
      },
      {
        id: 'm2',
        from: 'advisor',
        text: "Good morning Michael. You're right to flag that. The tech weighting moved to 32% due to appreciation. I'd recommend trimming back to our target of 28%.",
        timestamp: '2026-07-28T09:45:00Z',
      },
      {
        id: 'm3',
        from: 'client',
        text: 'That makes sense. Can we discuss this in our meeting tomorrow? Also curious about the new infrastructure fund you mentioned.',
        timestamp: '2026-07-28T10:20:00Z',
      },
      {
        id: 'm4',
        from: 'advisor',
        text: "Absolutely, I'll prepare a comparison sheet for the infrastructure fund. See you at 10 AM tomorrow.",
        timestamp: '2026-07-28T10:35:00Z',
      },
    ],
  },
  {
    id: 'thread-2',
    clientName: 'Sarah Johnson',
    clientEmail: 'sarah.johnson@email.com',
    messages: [
      {
        id: 'm5',
        from: 'advisor',
        text: "Hi Sarah, just a reminder that your annual compliance review is coming up next week. I'll need updated KYC documentation.",
        timestamp: '2026-07-27T14:00:00Z',
      },
      {
        id: 'm6',
        from: 'client',
        text: "Thanks for the heads up. I'll have my assistant send over the updated documents by Thursday.",
        timestamp: '2026-07-27T15:30:00Z',
      },
      {
        id: 'm7',
        from: 'advisor',
        text: 'Perfect. Also wanted to let you know your portfolio is up 8.2% YTD. The fixed income allocation has been performing particularly well.',
        timestamp: '2026-07-27T15:45:00Z',
      },
    ],
  },
  {
    id: 'thread-3',
    clientName: 'David Lee',
    clientEmail: 'david.lee@email.com',
    messages: [
      {
        id: 'm8',
        from: 'client',
        text: 'I saw the market drop this morning. Should I be concerned about my equity positions?',
        timestamp: '2026-07-29T08:30:00Z',
      },
      {
        id: 'm9',
        from: 'advisor',
        text: 'The S&P pulled back 1.8% on rate concerns, but this is within normal volatility. Your portfolio is well-diversified and the hedging positions are performing as expected.',
        timestamp: '2026-07-29T08:50:00Z',
      },
      {
        id: 'm10',
        from: 'client',
        text: "Good to hear. Let's keep the current strategy then. Can we review the options overlay in our 4pm meeting?",
        timestamp: '2026-07-29T09:10:00Z',
      },
      {
        id: 'm11',
        from: 'advisor',
        text: "Of course. I'll pull the current Greeks and P&L on the protective puts. See you at 4.",
        timestamp: '2026-07-29T09:20:00Z',
      },
    ],
  },
  {
    id: 'thread-4',
    clientName: 'Emma Wilson',
    clientEmail: 'emma.wilson@email.com',
    messages: [
      {
        id: 'm12',
        from: 'client',
        text: "Hi, I'd like to increase my monthly contribution to the superannuation account. Can we bump it to $5,000/month?",
        timestamp: '2026-07-26T11:00:00Z',
      },
      {
        id: 'm13',
        from: 'advisor',
        text: "Hi Emma, great idea given the concessional cap increase. I'll process the change — it'll take effect from next month's cycle.",
        timestamp: '2026-07-26T11:30:00Z',
      },
      {
        id: 'm14',
        from: 'client',
        text: 'Wonderful, thank you. Also, my husband and I are looking at purchasing an investment property. Can we discuss how that fits into the overall plan?',
        timestamp: '2026-07-26T12:15:00Z',
      },
      {
        id: 'm15',
        from: 'advisor',
        text: "Absolutely. I'll model a few scenarios for our quarterly review tomorrow. We should consider the impact on your debt-to-income ratio and portfolio liquidity.",
        timestamp: '2026-07-26T13:00:00Z',
      },
    ],
  },
  {
    id: 'thread-5',
    clientName: 'Robert Park',
    clientEmail: 'robert.park@email.com',
    messages: [
      {
        id: 'm16',
        from: 'advisor',
        text: 'Robert, your tax loss harvesting report is ready. We realised $42K in losses that can offset your capital gains this FY.',
        timestamp: '2026-07-25T16:00:00Z',
      },
      {
        id: 'm17',
        from: 'client',
        text: 'Excellent work. That should help significantly with the tax bill. Can you send me the detailed breakdown?',
        timestamp: '2026-07-25T17:00:00Z',
      },
      {
        id: 'm18',
        from: 'advisor',
        text: 'Sent to your email just now. Happy to walk through it in our session on Thursday if you have questions.',
        timestamp: '2026-07-25T17:15:00Z',
      },
    ],
  },
];
