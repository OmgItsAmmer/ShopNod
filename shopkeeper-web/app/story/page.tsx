import type { Metadata } from 'next';
import { StoryPlayer } from '@/components/story/story-player';
import './story.css';

export const metadata: Metadata = { title: 'The 60-second story' };

/** One click for judges: the whole life cycle, both screens side by side, running on the real app. */
export default function StoryPage() {
  return <StoryPlayer />;
}
