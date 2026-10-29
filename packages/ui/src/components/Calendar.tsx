import { useState } from 'react';
import { PageLayout } from './PageLayout';
import { UPCOMING_MEETINGS } from '../data/seed';
import type { Meeting } from '../data/seed';

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  date.setDate(diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function formatDateRange(monday: Date): string {
  const friday = new Date(monday);
  friday.setDate(monday.getDate() + 4);
  const opts: Intl.DateTimeFormatOptions = { month: 'long', day: 'numeric' };
  const start = monday.toLocaleDateString('en-AU', opts);
  const end = friday.toLocaleDateString('en-AU', { ...opts, year: 'numeric' });
  return `${start} – ${end}`;
}

function getDayLabel(monday: Date, offset: number): string {
  const d = new Date(monday);
  d.setDate(monday.getDate() + offset);
  return d.toLocaleDateString('en-AU', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

function getDateString(monday: Date, offset: number): string {
  const d = new Date(monday);
  d.setDate(monday.getDate() + offset);
  return d.toISOString().split('T')[0];
}

function MeetingCard({ meeting }: { meeting: Meeting }) {
  return (
    <div className="bg-blue-50 border-l-4 border-blue-500 rounded-r-lg p-3 mb-2">
      <p className="font-medium text-gray-900 text-sm">{meeting.clientName}</p>
      <p className="text-xs text-gray-500">{meeting.time}</p>
      <p className="text-xs text-blue-600 mt-0.5">{meeting.type}</p>
    </div>
  );
}

export function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => getMonday(new Date()));

  const prevWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() - 7);
    setWeekStart(d);
  };

  const nextWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + 7);
    setWeekStart(d);
  };

  const today = () => setWeekStart(getMonday(new Date()));

  const weekDates = Array.from({ length: 5 }, (_, i) =>
    getDateString(weekStart, i),
  );

  const meetingsByDay = weekDates.map((dateStr) =>
    UPCOMING_MEETINGS.filter((m) => m.date === dateStr),
  );

  const upcomingFromToday = UPCOMING_MEETINGS.filter(
    (m) => m.date >= new Date().toISOString().split('T')[0],
  )
    .sort(
      (a, b) => a.date.localeCompare(b.date) || a.time.localeCompare(b.time),
    )
    .slice(0, 5);

  return (
    <PageLayout title="Calendar">
      {/* Week navigation */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between">
        <button
          onClick={prevWeek}
          className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          &larr; Previous Week
        </button>
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">
            {formatDateRange(weekStart)}
          </h2>
          <button
            onClick={today}
            className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded font-medium hover:bg-blue-200 transition-colors"
          >
            Today
          </button>
        </div>
        <button
          onClick={nextWeek}
          className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
        >
          Next Week &rarr;
        </button>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Weekly grid */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-gray-200 p-4">
          <div className="grid grid-cols-5 gap-3">
            {weekDates.map((dateStr, i) => {
              const isToday =
                dateStr === new Date().toISOString().split('T')[0];
              return (
                <div key={dateStr} className="min-h-[200px]">
                  <div
                    className={`text-center text-xs font-medium py-2 rounded-t-lg mb-2 ${
                      isToday
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {getDayLabel(weekStart, i)}
                  </div>
                  {meetingsByDay[i].length === 0 ? (
                    <p className="text-xs text-gray-300 text-center mt-4">
                      No meetings
                    </p>
                  ) : (
                    meetingsByDay[i].map((m) => (
                      <MeetingCard key={m.id} meeting={m} />
                    ))
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Upcoming sidebar */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-800 mb-3">Upcoming</h3>
          {upcomingFromToday.length === 0 ? (
            <p className="text-sm text-gray-400">No upcoming meetings</p>
          ) : (
            <div className="space-y-3">
              {upcomingFromToday.map((m) => (
                <div
                  key={m.id}
                  className="border-b border-gray-50 pb-3 last:border-0"
                >
                  <p className="font-medium text-sm text-gray-900">
                    {m.clientName}
                  </p>
                  <p className="text-xs text-gray-500">
                    {new Date(m.date).toLocaleDateString('en-AU', {
                      weekday: 'short',
                      day: 'numeric',
                      month: 'short',
                    })}{' '}
                    at {m.time}
                  </p>
                  <p className="text-xs text-blue-600">{m.type}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
