import { Devvit } from '@devvit/public-api';

export const appSettings: Devvit.Setting[] = [
  {
    type: 'string',
    name: 'tiers',
    label: 'Karma Tiers (JSON format)',
    helpText: 'Define karma thresholds and post limits as a JSON array. Use `null` for infinity.',
    defaultValue: JSON.stringify(
      [
        { maxKarma: 250, limit: 1 },
        { maxKarma: 500, limit: 2 },
        { maxKarma: null, limit: 4 }, // null represents infinity
      ],
      null,
      2
    ),
  },
];

Devvit.addSettings(appSettings);