// The AIConsole Project
//
// Copyright 2023 10Clouds
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { TopBar } from '@/components/system/TopBar';
import { ProjectCard } from './ProjectCard';
import { useAICStore } from '@/store/AICStore';
import { RecentProjectsEmpty } from './RecentProjectsEmpty';
import { useRecentProjectsStore } from '@/store/home/useRecentProjectsStore';
import { useSettings } from '@/store/useSettings';

export function Home() {
  const openAiApiKey = useSettings((state) => state.openAiApiKey);
  const isApiKeyValid = useSettings((state) => state.isApiKeyValid);
  const isProjectLoading = useAICStore((state) => state.isProjectLoading);
  const recentProjects = useRecentProjectsStore(
    (state) => state.recentProjects,
  );
  return (
    <div className="min-h-[100vh] bg-recent-bg bg-cover bg-top">
      <div>
        {openAiApiKey === undefined || isProjectLoading ? (
          <>
            {/* the request is in progress - don't render anything to avoid flickering */}
          </>
        ) : (
          <>
            {recentProjects.length > 0 && openAiApiKey && isApiKeyValid ? (
              <>
                <TopBar variant="recentProjects" />
                <div className="px-[60px] py-[40px] text-white ">
                  <img
                    src="favicon.svg"
                    className="shadows-lg w-[60px] h-[60px] mx-auto m-4"
                    alt="Logo"
                  />
                  <h1 className="text-[56px] mb-[60px] font-black text-center">
                    Welcome to <span className=" text-primary">AIConsole!</span>
                  </h1>
                  <div className="p-4 pb-8 text-center opacity-75">
                    Recent projects:
                  </div>
                  <div className="grid grid-flow-row-dense grid-cols-[repeat(auto-fit,minmax(355px,_435px))] justify-center gap-[20px] mx-auto">
                    {recentProjects.map(({ name, path, recent_chats }) => (
                      <ProjectCard
                        key={path}
                        name={name}
                        path={path}
                        chatHistory={recent_chats}
                      />
                    ))}
                  </div>
                </div>
              </>
            ) : null}
            {!recentProjects.length || !openAiApiKey || !isApiKeyValid ? (
              <RecentProjectsEmpty
                openAiApiKey={openAiApiKey}
                isApiKeyValid={isApiKeyValid}
              />
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}