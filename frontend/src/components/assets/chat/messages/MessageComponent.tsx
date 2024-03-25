import { Ref, useCallback, useState } from 'react';
import { cn } from '@/utils/common/cn';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import rehypeRaw from 'rehype-raw';
import { duotoneDark as vs2015 } from 'react-syntax-highlighter/dist/cjs/styles/prism';

import { BlinkingCursor } from '@/components/assets/chat/BlinkingCursor';
import { useChatStore } from '@/store/assets/chat/useChatStore';
import { useAPIStore } from '@/store/useAPIStore';
import { EditableContentMessage } from './EditableContentMessage';
import { AICMessage, AICMessageGroup, getMessageLocation } from '../../../../types/assets/chatTypes';
import { ToolCall } from './ToolCall';

const urlRegex = /^https?:\/\//;

interface MessageProps {
  group: AICMessageGroup;
  message: AICMessage;
}

export function MessageComponent({ message, group }: MessageProps) {
  const userMutateChat = useChatStore((state) => state.userMutateChat);
  const saveCommandAndMessagesToHistory = useChatStore((state) => state.saveCommandAndMessagesToHistory);
  const getBaseURL = useAPIStore((state) => state.getBaseURL);
  const [isEditing, setIsEditing] = useState(false);
  const chat = useChatStore((state) => state.chat);

  const handleRemoveClick = useCallback(() => {
    if (group.messages.length < 2) {
      userMutateChat({
        type: 'DeleteMutation',
        ref: {
          id: group.id,
          parent_collection: {
            id: 'message_groups',
            parent: { id: chat?.id, parent_collection: { id: 'assets', parent: null } },
          },
        },
      });
      return;
    }

    userMutateChat({
      type: 'DeleteMutation',
      ref: {
        id: message.id,
        parent_collection: {
          id: 'messages',
          parent: {
            id: group.id,
            parent_collection: {
              id: 'message_groups',
              parent: { id: chat?.id, parent_collection: { id: 'assets', parent: null } },
            },
          },
        },
      },
    });
  }, [message.id, userMutateChat]);

  const handleSaveClick = useCallback(
    async (content: string) => {
      await userMutateChat({
        type: 'SetValueMutation',
        ref: {
          id: message.id,
          parent_collection: {
            id: 'messages',
            parent: {
              id: group.id,
              parent_collection: {
                id: 'message_groups',
                parent: { id: chat?.id, parent_collection: { id: 'assets', parent: null } },
              },
            },
          },
        },
        key: 'content',
        value: content,
      });

      saveCommandAndMessagesToHistory(content, group.role === 'user');
    },
    [message.id, saveCommandAndMessagesToHistory, group.role, userMutateChat],
  );

  const submitCommand = useChatStore((state) => state.submitCommand);

  return (
    <div>
      <EditableContentMessage
        enableTTS={!!message.content}
        initialContent={message.content}
        handleAcceptedContent={handleSaveClick}
        handleRemoveClick={handleRemoveClick}
        hideControls
        isEditing={isEditing}
        setIsEditing={setIsEditing}
      >
        <div className="flex flex-col gap-2">
          {message.is_streaming && !message.content && message.tool_calls.length === 0 && <BlinkingCursor />}
          {message.content && (
            <div className="max-w-[700px]">
              {group.role !== 'user' && (
                <div className="flex-grow">
                  <div className="prose prose-stone dark:prose-invert sidebar-typography w-full max-w-full">
                    <ReactMarkdown
                      urlTransform={null}
                      rehypePlugins={[rehypeRaw]}
                      components={{
                        // eslint-disable-next-line @typescript-eslint/no-unused-vars
                        a: ({ node, href, ...props }) => {
                          if (href === 'command') {
                            const command = (Array.isArray(props.children) ? props.children[0]?.toString() : '') ?? '';

                            return (
                              <a
                                {...props}
                                className="text-secondary hover:text-secondary-light cursor-pointer"
                                onClick={() => {
                                  submitCommand(command ? command : props.children);
                                }}
                              >
                                {props.children}
                              </a>
                            );
                          }
                          return (
                            <a
                              href={href}
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary"
                            >
                              {props.children}
                            </a>
                          );
                        },
                        img: ({ src, ...props }) => {
                          const imgSrc = urlRegex.test(src || '') ? src : `${getBaseURL()}/image?path=${src}`;
                          return (
                            <a href={imgSrc} target="_blank">
                              <img src={imgSrc} {...props} className=" max-w-xs rounded-md mr-5" alt={props.alt} />
                            </a>
                          );
                        },
                        code(props) {
                          // eslint-disable-next-line @typescript-eslint/no-unused-vars
                          const { children, className, node, ref, ...rest } = props;
                          const match = /language-(\w+)/.exec(className || '');
                          return match ? (
                            <SyntaxHighlighter
                              {...rest}
                              ref={ref as Ref<SyntaxHighlighter>}
                              style={vs2015}
                              children={String(children).replace(/\n$/, '')}
                              language={match[1]}
                              PreTag="div"
                            />
                          ) : (
                            <code {...rest} className={className}>
                              {children}
                            </code>
                          );
                        },
                        ol(props) {
                          // eslint-disable-next-line @typescript-eslint/no-unused-vars
                          const { children, className, node, ...rest } = props;
                          return (
                            <ol className={cn('ml-[8px]', className)} {...rest}>
                              {children}
                            </ol>
                          );
                        },
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
              {group.role === 'user' && (
                <div className="flex-grow">
                  {message.content.split('\n').map((line, index) => (
                    <span key={`line-${index}`} style={{ whiteSpace: 'pre-wrap' }}>
                      {line}
                      {index !== message.content.split('\n').length - 1 && <br />}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          {!message.is_streaming &&
            message.tool_calls.map((toolCall) => <ToolCall key={toolCall.id} group={group} toolCall={toolCall} />)}
        </div>
      </EditableContentMessage>
    </div>
  );
}
