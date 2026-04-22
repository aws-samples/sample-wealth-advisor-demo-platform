import * as url from 'url';
import { Construct } from 'constructs';
import { StaticWebsite } from '../../core/index.js';

export class Ui extends StaticWebsite {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      websiteName: 'Ui',
      websiteFilePath: url.fileURLToPath(
        new URL('../../../../../../dist/packages/ui/bundle', import.meta.url),
      ),
    });
  }
}
