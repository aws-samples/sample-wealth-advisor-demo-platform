import * as url from 'url';
import { Construct } from 'constructs';
import { StaticWebsite } from '../../core/index.js';

export class Website extends StaticWebsite {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      websiteName: 'Website',
      websiteFilePath: url.fileURLToPath(
        new URL(
          '../../../../../../dist/packages/website/bundle',
          import.meta.url,
        ),
      ),
    });
  }
}
